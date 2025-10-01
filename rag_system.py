"""Command-line script to build and query a PDF RAG index with LlamaIndex.

This script replicates the step-by-step workflow outlined in the prompt while
remaining compatible with a standard Python environment (no Colab-specific
APIs).  It loads PDF files from a directory, builds a vector index using
OpenAI-powered embeddings, runs a couple of sample questions, and finally
starts an interactive question/answer loop.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI


def _print_step(title: str) -> None:
    """Print a highlighted step heading."""

    print("=" * 60)
    print(title)
    print("=" * 60)


def _build_index(data_dir: str, top_k: int, response_mode: str) -> VectorStoreIndex:
    print("📖 Loading documents...")
    documents = SimpleDirectoryReader(data_dir).load_data()
    if not documents:
        raise ValueError(
            f"No documents found in '{data_dir}'. Add at least one PDF or text file."
        )
    print(f"✓ Loaded {len(documents)} document(s)")
    total_chars = sum(len(doc.text) for doc in documents)
    print(f"✓ Characters: {total_chars:,}\n")

    print("🧠 Building vector index with OpenAI embeddings...")
    index = VectorStoreIndex.from_documents(documents, show_progress=True)
    print("\n✓ Index created!\n")

    return index


def _run_sample_questions(index: VectorStoreIndex, questions: Sequence[str], top_k: int, response_mode: str) -> None:
    print("TESTING THE INDEX")
    query_engine = index.as_query_engine(
        similarity_top_k=top_k,
        response_mode=response_mode,
    )

    for i, question in enumerate(questions, start=1):
        print(f"Q{i}: {question}")
        print("-" * 60)
        response = query_engine.query(question)
        print(f"A: {response}\n\n")


def _interactive_loop(index: VectorStoreIndex, top_k: int, response_mode: str) -> None:
    chat_engine = index.as_chat_engine(chat_mode="context")
    print("INTERACTIVE Q&A MODE")
    print("Type 'exit', 'quit', or 'q' to leave the session.\n")

    while True:
        try:
            question = input("Your question: ")
        except (KeyboardInterrupt, EOFError):
            print("\n✅ Done!")
            break

        if question.strip().lower() in {"exit", "quit", "q"}:
            print("\n✅ Done!")
            break
        if not question.strip():
            continue

        response = chat_engine.chat(question)
        print(f"\nAnswer: {response}")
        print("-" * 60)


def _configure_models(model: str, embedding_model: str) -> None:
    Settings.llm = OpenAI(model=model)
    Settings.embed_model = OpenAIEmbedding(model=embedding_model)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and query a RAG index from PDFs.")
    parser.add_argument(
        "data_dir",
        nargs="?",
        default="data",
        help="Directory containing PDF/text files (default: ./data)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI chat completion model to use (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model to use (default: text-embedding-3-small)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top similar chunks to retrieve per query (default: 3)",
    )
    parser.add_argument(
        "--response-mode",
        default="compact",
        help="Response mode passed to the query engine (default: compact)",
    )
    parser.add_argument(
        "--skip-interactive",
        action="store_true",
        help="Skip the interactive Q&A session.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set the OPENAI_API_KEY environment variable before running.", file=sys.stderr)
        return 1

    os.makedirs(args.data_dir, exist_ok=True)
    print("✓ Data directory verified\n")

    print("🔑 Configuring OpenAI models...")
    _configure_models(model=args.model, embedding_model=args.embedding_model)
    print(f"✓ Chat model: {args.model}")
    print(f"✓ Embedding model: {args.embedding_model}\n")

    index = _build_index(args.data_dir, top_k=args.top_k, response_mode=args.response_mode)

    _print_step("Sample Questions")
    sample_questions = [
        "What are the main topics in these documents?",
        "Provide a detailed summary with key insights.",
    ]
    _run_sample_questions(index, sample_questions, args.top_k, args.response_mode)

    if not args.skip_interactive:
        _print_step("Interactive Session")
        _interactive_loop(index, args.top_k, args.response_mode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
