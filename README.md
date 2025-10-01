# Excel-vba

This repository contains both the original Excel-to-SAP demonstration module
and a Python example that walks through building a retrieval-augmented
generation (RAG) system inspired by the provided prompt.

## SAP HANA 4.0 Example

The module `SAP_HANA_Connection.bas` demonstrates connecting to an SAP HANA
database from Excel VBA.

1. Install the SAP HANA ODBC driver on your machine.
2. In the VBA editor, go to **Tools > References** and enable *Microsoft
   ActiveX Data Objects*.
3. Import `SAP_HANA_Connection.bas` into your VBA project.
4. Run `LoginAndQuery` to be prompted for the server address, user name, and
   password and write sample data to the active sheet, or call `GetHanaData`
   directly with your own parameters.
5. Use the returned recordset to populate a worksheet or otherwise consume the
   data.

## Python RAG Example

The script `rag_system.py` is a command-line adaptation of the “Complete RAG
system with GPT-5” workflow. It uses LlamaIndex with OpenAI models to build a
vector index from local documents and provides both sample questions and an
interactive Q&A loop.

### Prerequisites

- Python 3.10+
- `OPENAI_API_KEY` environment variable set with a valid key
- The Python packages listed in the prompt (`llama-index`,
  `llama-index-embeddings-openai`, `llama-index-llms-openai`,
  `llama-index-readers-file`, `pypdf`). Install them with:

  ```bash
  pip install llama-index llama-index-embeddings-openai \
      llama-index-llms-openai llama-index-readers-file pypdf
  ```

### Usage

1. Place PDF or text files inside a data directory (defaults to `./data`).
2. Run the script:

   ```bash
   python rag_system.py
   ```

   Optional arguments let you specify the data directory, chat model, embedding
   model, retrieval depth, and response mode. Use `python rag_system.py --help`
   for details.
3. The script loads your documents, builds the vector index, prints answers to
   two sample questions, and then starts an interactive chat session. Exit by
   typing `exit`, `quit`, or `q`.
