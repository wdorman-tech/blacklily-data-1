"""T3 grounded Q&A with abstention: one DDQ question answered from the firm's own documents."""

from __future__ import annotations

JSON_MODE = True
NUM_PREDICT = 768
ABSTAIN = "NOT_IN_DOCUMENTS"

SYSTEM = f"""You are an investor relations and operations analyst at a registered \
investment adviser. You answer due diligence questionnaire (DDQ) questions from \
prospective institutional clients using only the firm's own documents, which are \
provided to you. A wrong answer in a DDQ is a misstatement to a client, so you never \
guess, never supply what firms like yours usually do, and never fill a gap from general \
knowledge.

Rules you follow without exception:

1. Answer only from the documents provided.
2. If the documents do not answer the question, or address the topic without giving the \
specific detail asked for (a limit, a date, a name, a frequency), the answer is exactly \
{ABSTAIN}.
3. Later-dated documents supersede earlier ones. Where a policy update memorandum or \
amendment changes a provision, answer with the provision currently in effect, not the \
original.
4. Keep answers short and specific: the number, name, frequency, threshold or rule that \
was asked for, with enough words to be unambiguous.
5. Cite the document file name and the section where the answer appears, as they are \
labelled in the documents.
6. Quote the supporting text verbatim."""

USER_TEMPLATE = """The firm documents are below, followed by one due diligence question to \
answer from them.

--- BEGIN DOCUMENTS ---
{context}
--- END DOCUMENTS ---

Question: {question}

Return ONLY a JSON object. No markdown fence, no preamble, no commentary. The object has \
exactly four string keys:

  "answer"          - the answer, or {abstain}
  "source_document" - the file name of the document that answers it, or "" if {abstain}
  "section"         - the section where the answer appears, or "" if {abstain}
  "quote"           - verbatim supporting text, or "" if {abstain}

JSON object only:"""


MAP_NUM_PREDICT = 6144
REDUCE_NUM_PREDICT = 6144

MAP_TEMPLATE = """The documents below are PART of a firm's document pack; other documents \
are shown separately. Answer each numbered due diligence question from THESE documents \
only. Where these documents do not answer a question, the answer is {abstain}.

--- BEGIN DOCUMENTS ---
{context}
--- END DOCUMENTS ---

Questions:
{questions}

Return ONLY a JSON object with one key, "answers": a list with one object per question, \
in order, each with exactly five string keys: "qid", "answer", "source_document", \
"section", "quote". Use {abstain} and empty strings where these documents do not answer.

JSON object only:"""

REDUCE_TEMPLATE = """A firm's document pack was read in parts. For each numbered due \
diligence question below you have the candidate answers found in each part, with the \
document each came from. The documents and their dates are:
{doc_list}

Give one final answer per question. Where candidates conflict, the later-dated document \
controls. Where no part answered, the answer is {abstain}.

{candidates}

Return ONLY a JSON object with one key, "answers": a list with one object per question, \
in order, each with exactly five string keys: "qid", "answer", "source_document", \
"section", "quote".

JSON object only:"""


def build_user(question: str, context: str) -> str:
    return USER_TEMPLATE.format(question=question.strip(), context=context.strip(), abstain=ABSTAIN)


def format_chunk(doc_name: str, doc_label: str, section: str, text: str) -> str:
    return f"<<< {doc_name} | {doc_label} | Section: {section} >>>\n{text.strip()}"


def format_document(doc_name: str, text: str) -> str:
    return f"<<< {doc_name} >>>\n{text.strip()}"
