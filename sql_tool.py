from __future__ import annotations
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import torch

import duckdb, pandas as pd
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
from config import DUCK_FILE, LABOR_XLSX, LABOR_SHEET
from rag import RAG

try:
    from transformers import T5ForConditionalGeneration, T5Tokenizer, AutoTokenizer
except Exception:
    T5ForConditionalGeneration = None
    T5Tokenizer = None

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_t5_model: Optional[T5ForConditionalGeneration] = None
_t5_tokenizer: Optional[T5Tokenizer] = None

def _ensure_duck():
    con = duckdb.connect(DUCK_FILE)
    df = pd.read_excel(LABOR_XLSX, sheet_name=LABOR_SHEET)
    df.columns = [str(c).strip() for c in df.columns]

    if "Posting Date" in df.columns:
        try:
            df["Posting Date"] = pd.to_datetime(df["Posting Date"], format="%m/%d/%y", errors="coerce")
        except Exception:
            pass
        df["Posting Date"] = pd.to_datetime(df["Posting Date"], errors="coerce")
        df = df.dropna(subset=["Posting Date"])

    if "Val.in rep.cur." in df.columns:
        df["Val.in rep.cur."] = pd.to_numeric(df["Val.in rep.cur."], errors="coerce").fillna(0.0)

    con.execute("DROP TABLE IF EXISTS labor_data")
    con.register("labor_df", df)
    con.execute("CREATE TABLE labor_data AS SELECT * FROM labor_df")
    return con

def sql_query_rag(template: str, params: Dict[str, Any], qctx: Optional[str] = None):
    con = _ensure_duck()
    month = params.get("month")
    year  = params.get("year")

    if not isinstance(month, int) or month < 1 or month > 12:
        month = datetime.utcnow().month
    if not isinstance(year, int) or year < 2000 or year > 2100:
        year = datetime.utcnow().year

    if template == "labor_cost_month_top1":
        sql = f"""
        WITH month_data AS (
          SELECT
            "CO Object Name" AS park,
            CAST("Val.in rep.cur." AS DOUBLE) AS cost,
            "Posting Date"::TIMESTAMP AS posting_dt
          FROM labor_data
        )
        SELECT park, SUM(cost) AS total_cost
        FROM month_data
        WHERE year(posting_dt) = {year}
          AND month(posting_dt) = {month}
        GROUP BY park
        ORDER BY total_cost DESC
        LIMIT 1;
        """
    else:
        sql = "SELECT 'unknown template' AS msg;"

    t0 = time.time()
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    elapsed = int((time.time()-t0)*1000)
    con.close()
    generated_sql = generate_sql_with_t5("Which park had the highest mowing cost in June 2025?",
   table_schema="""CREATE TABLE labor_data (posting_dt TIMESTAMP,
   "park" TEXT, 
   "mowing_cost" DOUBLE);""")
    print("Generated SQL_Gauss:", generate_with_gaussalgo())
    print("Generated SQL_sqlcoder:", generate_sql_with_sqlcoder("Which park has most mowing cost in March 2025?"))
    support = RAG.retrieve(qctx or "mowing labor cost pricing frequency lane kilometer hourly rate standard", k=3)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": elapsed, "support": support}

def _init_t5():
    global _t5_model, _t5_tokenizer
    if _t5_model is not None and _t5_tokenizer is not None:
        return
    if T5ForConditionalGeneration is None or (T5Tokenizer is None and AutoTokenizer is None):
        raise RuntimeError("transformers not available; pip install transformers[torch]")

    model_id = "suriya7/t5-base-text-to-sql"
    # simple load using AutoTokenizer (fallback to T5Tokenizer supported by HF)
    if AutoTokenizer is not None:
        _t5_tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=False)
    else:
        _t5_tokenizer = T5Tokenizer.from_pretrained(model_id)

    _t5_model = T5ForConditionalGeneration.from_pretrained(model_id).to(_device)
    _t5_model.eval()
    try:
        setattr(_t5_model, "name_or_path", model_id)
    except Exception:
        pass

def generate_sql_with_t5(
    nl_query: str,
    table_schema: Optional[str] = None,
    max_length: int = 256,
    num_beams: int = 3,
    num_return_sequences: int = 1,
    model_name: str = "suriya7/t5-base-text-to-sql"
) -> List[str]:
    """
    Convert a natural-language query to SQL using T5.
    """
    # allow switching model if needed (re-init if different)

    _init_t5()
    global _t5_model, _t5_tokenizer
    if _t5_model is None or getattr(_t5_model, "name_or_path", None) != model_name:
        # re-init with requested model
        _t5_model = None
        _t5_tokenizer = None
        # load the requested model
        if T5ForConditionalGeneration is None or T5Tokenizer is None:
            raise RuntimeError("transformers not available; pip install transformers[torch]")
        _t5_tokenizer = T5Tokenizer.from_pretrained(model_name)
        _t5_model = T5ForConditionalGeneration.from_pretrained(model_name).to(_device)
        _t5_model.eval()
        setattr(_t5_model, "name_or_path", model_name)
    print("i am here")
    # build few-shot prompt
    examples = [
        ("Which park had the highest mowing cost in January 2025?",
         """
        SELECT park, mowing_cost
        FROM labor_data
        WHERE year(posting_dt) = 2025
          AND month(posting_dt) = 1
        GROUP BY park
        ORDER BY mowing_cost DESC
        LIMIT 1;
        """),
        ("Which park had the highest mowing cost in February 2025?",
         """
        SELECT park, mowing_cost
        FROM labor_data
        WHERE year(posting_dt) = 2025
          AND month(posting_dt) = 2
        GROUP BY park
        ORDER BY mowing_cost DESC
        LIMIT 1;
        """),
        ("Which park had the highest mowing cost in January 2026?",
         """
        SELECT park, mowing_cost
        FROM labor_data
        WHERE year(posting_dt) = 2026
          AND month(posting_dt) = 1
        GROUP BY park
        ORDER BY mowing_cost DESC
        LIMIT 1;
        """)
    ]
    few_shot = "\n\n".join([f"NL: {q}\nSQL: {s}" for q, s in examples])

    header = f"Schema: {table_schema}\n\n" if table_schema else ""
    prompt = f"{header}Translate the following natural language to executable SQL. Provide only the SQL (no explanation).\n\n{few_shot}\n\nNL: {nl_query}\nSQL:"

    # defensive checks / debug info
    if _t5_tokenizer is None:
        raise RuntimeError("tokenizer not initialized")

    try:
        # tokenize, then move tensors to device explicitly (avoid calling .to on BatchEncoding)
        inputs = _t5_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(_device) for k, v in inputs.items()}
    except Exception as e:
        # provide clearer debug info
        raise RuntimeError(f"tokenizer failed: {e}; prompt type={type(prompt)} model_name={type(model_name)}") from e

    gen_kwargs = {
        "max_length": max_length,
        "num_beams": num_beams,
        "early_stopping": True,
        "num_return_sequences": max(1, num_return_sequences),
    }
    with torch.no_grad():
        outputs = _t5_model.generate(**inputs, **gen_kwargs)

    results = []
    for out in outputs:
        sql = _t5_tokenizer.decode(out, skip_special_tokens=True).strip()
        if nl_query.lower() in sql.lower() or sql.startswith(prompt[: min(200, len(prompt))]):
            results.append("") 
        else:
            results.append(sql)
    print("Generated SQL:", results)
    return results

# Example usage (in code):
# sqls = generate_sql_with_t5("Which park had the highest mowing cost in March 2025?",
#                            table_schema="labor_data(posting_dt TIMESTAMP, CO Object Name TEXT, Val.in rep.cur. DOUBLE)")
# print(sqls[0])

def generate_with_gaussalgo():
    model_path = 'gaussalgo/T5-LM-Large-text2sql-spider'
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    question = "Which park has most mowing cost in March 2025?"
    schema = """
    "park_mowing" "Park_ID" int , "mowing_cost" double , "Park_Name" text , "Posting_Date" date
    """

    input_text = " ".join(["Question: ",question, "Schema:", schema])

    model_inputs = tokenizer(input_text, return_tensors="pt")
    outputs = model.generate(**model_inputs, max_length=512)

    output_text = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    return output_text
def get_tokenizer_model(model_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        device_map="auto",
        use_cache=True,
    )
    return tokenizer, model

def generate_prompt(question, prompt_file="prompt.md", metadata_file="metadata.sql"):
    with open(prompt_file, "r") as f:
        prompt = f.read()
    
    with open(metadata_file, "r") as f:
        table_metadata_string = f.read()

    prompt = prompt.format_map({"user_question": question, "table_metadata_string_DDL": table_metadata_string})
    return prompt

def generate_sql_with_sqlcoder(question, prompt_file="prompt.md", metadata_file="metadata.sql"):
    tokenizer, model = get_tokenizer_model("defog/sqlcoder-7b-2")
    prompt = generate_prompt(question, prompt_file, metadata_file)
    print("Prompt:", prompt)
    # make sure the model stops generating at triple ticks
    # eos_token_id = tokenizer.convert_tokens_to_ids(["```"])[0]
    eos_token_id = tokenizer.eos_token_id
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=300,
        do_sample=False,
        return_full_text=False, # added return_full_text parameter to prevent splitting issues with prompt
        num_beams=5, # do beam search with 5 beams for high quality results
    )
    generated_query = (
        pipe(
            prompt,
            num_return_sequences=1,
            eos_token_id=eos_token_id,
            pad_token_id=eos_token_id,
        )[0]["generated_text"]
        .split(";")[0]
        .split("```")[0]
        .strip()
        + ";"
    )
    return generated_query
