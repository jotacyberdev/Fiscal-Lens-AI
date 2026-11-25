import re
import sqlite3
from pathlib import Path
from typing import List, Optional
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class ConsultaBIResponse(BaseModel):
    sql_query: str = Field(
        description="Consulta SQLite válida começando estritamente com SELECT. Nunca use INSERT, UPDATE, DELETE, DROP, ALTER ou PRAGMA."
    )
    explicacao_curta: str = Field(
        description="Resumo claro e executivo em português explicando o que os dados retornados mostram."
    )
    tipo_visualizacao: str = Field(
        description="Escolha entre: 'tabela', 'barras' (quando houver categoria/fornecedor + valor numérico) ou 'metrica' (quando retornar apenas 1 número)."
    )


class AnalistaBIFiscal:
    def __init__(self, api_key: str, db_path: str = "notas_fiscais.db", model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.db_path = Path(db_path)
        self.model_name = model_name

    def _validar_sql_somente_leitura(self, sql: str) -> str:
        """Trava de segurança contra SQL Injection e comandos destrutivos."""
        sql_limpo = sql.strip().rstrip(";")
        if not sql_limpo.upper().startswith("SELECT"):
            raise ValueError("Bloqueio de segurança: apenas consultas SELECT são permitidas.")

        comandos_proibidos = r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM)\b"
        if re.search(comandos_proibidos, sql_limpo, flags=re.IGNORECASE):
            raise ValueError("Bloqueio de segurança: comando SQL não autorizado detectado.")

        if ";" in sql_limpo:
            raise ValueError("Bloqueio de segurança: múltiplas instruções SQL não são permitidas.")

        return sql_limpo

    def responder_pergunta(
        self,
        pergunta: str,
        cargo: str,
        categorias_permitidas: Optional[List[str]] = None,
    ) -> dict:
        """Traduz a pergunta em português para SQL respeitando o RBAC do usuário e executa no SQLite."""
        regra_rbac = (
            "O usuário tem perfil ADMIN/FINANCEIRO e pode consultar todas as categorias sem restrição."
            if not categorias_permitidas
            else f"RESTRIÇÃO OBRIGATÓRIA DE RBAC (Cargo: {cargo}): Você DEVE incluir na cláusula WHERE da query SQL o filtro: categoria_sugerida IN ({', '.join(repr(c) for c in categorias_permitidas)}). Nunca retorne dados fora dessas categorias."
        )

        prompt_sistema = f"""
Você é um Analista de BI Financeiro Sênior especialista em SQLite.
Traduza a pergunta do usuário em uma consulta SQLite precisa sobre a tabela `documentos_fiscais`.

Esquema da tabela `documentos_fiscais`:
- id (INTEGER)
- nome_arquivo (TEXT)
- tipo_documento (TEXT: 'NFe', 'NFSe', 'NFCe', 'Recibo', 'Boleto', 'Outro')
- numero_documento (TEXT)
- data_emissao (TEXT no formato 'AAAA-MM-DD')
- cnpj_emissor (TEXT)
- nome_emissor (TEXT)
- valor_descontos (REAL)
- valor_frete (REAL)
- valor_acrescimos (REAL)
- valor_total_documento (REAL)
- categoria_sugerida (TEXT: 'Alimentação', 'Transporte', 'Software', 'Material de Escritório', 'Serviços Terceiros', 'Utilidades', 'Outros')
- status_aprovacao (TEXT: 'Aprovado Auto', 'Aprovado Manualmente')
- criado_em (TIMESTAMP)

Regras obrigatórias:
1. Gere APENAS consultas SELECT.
2. Dê apelidos (AS) legíveis em português às colunas retornadas (ex.: `SUM(valor_total_documento) AS total_gasto`).
3. {regra_rbac}
"""

        resposta = self.client.models.generate_content(
            model=self.model_name,
            contents=[prompt_sistema, f"Pergunta do usuário: {pergunta}"],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ConsultaBIResponse,
                temperature=0.0,
            ),
        )

        resultado_ia = ConsultaBIResponse.model_validate_json(resposta.text)
        sql_seguro = self._validar_sql_somente_leitura(resultado_ia.sql_query)

        with sqlite3.connect(self.db_path) as conn:
            df_resultado = pd.read_sql_query(sql_seguro, conn)

        return {
            "sql": sql_seguro,
            "explicacao": resultado_ia.explicacao_curta,
            "visualizacao": resultado_ia.tipo_visualizacao,
            "dados": df_resultado,
        }