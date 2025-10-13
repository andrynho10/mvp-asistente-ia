from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd
import typer
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from sklearn.feature_extraction.text import TfidfVectorizer

from config.settings import get_settings
from src.knowledge_base.text_cleaning import clean_text

try:
    from langchain_community.document_loaders import Docx2txtLoader
except ImportError:  # pragma: no cover - dependencia opcional
    Docx2txtLoader = None

try:
    from langchain_community.document_loaders import PyPDFLoader
except ImportError:  # pragma: no cover - dependencia opcional
    PyPDFLoader = None

SUPPORTED_SUFFIXES = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".pdf",
    ".docx",
}
DEFAULT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", " ", ""],
)

SPANISH_STOP_WORDS = [
    "a",
    "ante",
    "con",
    "de",
    "del",
    "desde",
    "donde",
    "durante",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "era",
    "eres",
    "es",
    "esa",
    "ese",
    "eso",
    "esta",
    "estaba",
    "estamos",
    "estan",
    "este",
    "esto",
    "ha",
    "habia",
    "han",
    "hasta",
    "la",
    "las",
    "lo",
    "los",
    "mas",
    "me",
    "mi",
    "mientras",
    "muy",
    "no",
    "nos",
    "nosotros",
    "o",
    "para",
    "pero",
    "por",
    "que",
    "se",
    "sin",
    "sobre",
    "su",
    "sus",
    "tambien",
    "te",
    "tiene",
    "tu",
    "un",
    "una",
    "uno",
    "y",
]

app = typer.Typer(help="Pipeline de ingesta y normalizacion de documentos organizacionales.")


@dataclass
class KnowledgeChunk:
    text: str
    metadata: Dict[str, object]


def discover_raw_files(raw_dir: Path) -> List[Path]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"No se encontro la carpeta de datos crudos: {raw_dir}")

    files = [
        path for path in raw_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    if not files:
        typer.echo("No se encontraron documentos en la carpeta raw/.")
    return files


def load_with_loader(path: Path) -> List[Document]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        loader = TextLoader(str(path), encoding="utf-8")
        return loader.load()
    if suffix == ".pdf":
        if PyPDFLoader is None:
            raise ImportError("PyPDFLoader no esta disponible. Instale la dependencia 'pypdf'.")
        loader = PyPDFLoader(str(path))
        return loader.load()
    if suffix == ".docx":
        if Docx2txtLoader is None:
            raise ImportError("Docx2txtLoader no esta disponible. Instale la dependencia 'docx2txt'.")
        loader = Docx2txtLoader(str(path))
        return loader.load()
    if suffix == ".csv":
        df = pd.read_csv(path)
        content = df.to_string(index=False)
        return [Document(page_content=content, metadata={"source": str(path)})]
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        content = json.dumps(data, ensure_ascii=False, indent=2)
        return [Document(page_content=content, metadata={"source": str(path)})]
    # fallback seguro
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [Document(page_content=text, metadata={"source": str(path)})]


def compute_keywords(chunks: Iterable[str], top_k: int = 5) -> List[List[str]]:
    texts = list(chunks)
    non_empty_chunks = [chunk for chunk in texts if chunk.strip()]
    if not non_empty_chunks:
        return [[] for _ in texts]

    vectorizer = TfidfVectorizer(max_features=50, stop_words=SPANISH_STOP_WORDS)
    tfidf_matrix = vectorizer.fit_transform(non_empty_chunks)
    feature_names = vectorizer.get_feature_names_out()
    keywords_per_chunk = []
    for row in tfidf_matrix:
        sorted_indices = row.toarray()[0].argsort()[::-1]
        keywords = [feature_names[idx] for idx in sorted_indices[:top_k]]
        keywords_per_chunk.append(keywords)

    result = []
    non_empty_iter = iter(keywords_per_chunk)
    for chunk in texts:
        if chunk.strip():
            result.append(next(non_empty_iter))
        else:
            result.append([])
    return result


def split_documents(documents: List[Document], splitter: RecursiveCharacterTextSplitter) -> List[Document]:
    cleaned_docs = []
    for doc in documents:
        cleaned_docs.append(
            Document(page_content=clean_text(doc.page_content), metadata=doc.metadata.copy())
        )
    return splitter.split_documents(cleaned_docs)


def build_chunks(
    raw_path: Path,
    base_metadata: Dict[str, object],
    splitter: RecursiveCharacterTextSplitter = DEFAULT_SPLITTER,
) -> List[KnowledgeChunk]:
    documents = load_with_loader(raw_path)

    split_docs = split_documents(documents, splitter)
    texts = [doc.page_content for doc in split_docs]
    keywords = compute_keywords(texts)

    chunks: List[KnowledgeChunk] = []
    for idx, doc in enumerate(split_docs):
        metadata = {
            **doc.metadata,
            **base_metadata,
            "chunk_id": f"{base_metadata['document_id']}#chunk-{idx}",
            "keywords": keywords[idx],
        }
        chunks.append(KnowledgeChunk(text=doc.page_content, metadata=metadata))
    return chunks


def persist_chunks(chunks: Iterable[KnowledgeChunk], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        for chunk in chunks:
            fp.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def run_ingestion() -> Path:
    settings = get_settings()
    raw_dir = settings.raw_data_path
    processed_dir = settings.knowledge_base_path
    processed_dir.mkdir(parents=True, exist_ok=True)

    splitter = DEFAULT_SPLITTER
    all_chunks: List[KnowledgeChunk] = []
    for file_path in discover_raw_files(raw_dir):
        base_metadata = {
            "document_id": file_path.stem,
            "source": str(file_path.relative_to(raw_dir)),
            "process": file_path.parts[-2] if len(file_path.parts) > 1 else "general",
        }
        chunks = build_chunks(file_path, base_metadata, splitter=splitter)
        all_chunks.extend(chunks)

    output_file = processed_dir / "knowledge_chunks.jsonl"
    persist_chunks(all_chunks, output_file)
    typer.echo(f"Se generaron {len(all_chunks)} chunks en {output_file}")
    return output_file


@app.command()
def ingest() -> None:
    """Ejecuta el pipeline de ingestion completo."""
    run_ingestion()


if __name__ == "__main__":
    app()
