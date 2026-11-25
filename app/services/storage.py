import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd


class RepositorioNotas:
    def __init__(self, db_path: str = "notas_fiscais.db"):
        self.db_path = Path(db_path)
        self._inicializar_banco()

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _inicializar_banco(self) -> None:
        with self._conectar() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documentos_fiscais (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_arquivo TEXT UNIQUE NOT NULL,
                    nome_arquivo TEXT,
                    tipo_documento TEXT,
                    numero_documento TEXT,
                    chave_acesso TEXT,
                    data_emissao TEXT,
                    cnpj_emissor TEXT,
                    nome_emissor TEXT,
                    cnpj_destinatario TEXT,
                    valor_descontos REAL,
                    valor_frete REAL,
                    valor_acrescimos REAL,
                    valor_total_documento REAL,
                    categoria_sugerida TEXT,
                    status_aprovacao TEXT,
                    alertas_json TEXT,
                    itens_json TEXT,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def arquivo_ja_processado(self, hash_arquivo: str) -> bool:
        with self._conectar() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM documentos_fiscais WHERE hash_arquivo = ?",
                (hash_arquivo,),
            )
            return cursor.fetchone() is not None

    def nota_duplicada(
        self, cnpj_emissor: str | None, numero_documento: str | None, valor_total: float
    ) -> bool:
        if not cnpj_emissor or not numero_documento:
            return False
        with self._conectar() as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM documentos_fiscais
                WHERE cnpj_emissor = ? AND numero_documento = ? AND ABS(valor_total_documento - ?) < 0.02
                """,
                (cnpj_emissor, numero_documento, valor_total),
            )
            return cursor.fetchone() is not None

    def salvar_lote(self, registros: List[Dict[str, Any]]) -> int:
        salvos = 0
        with self._conectar() as conn:
            for reg in registros:
                try:
                    conn.execute(
                        """
                        INSERT INTO documentos_fiscais (
                            hash_arquivo, nome_arquivo, tipo_documento, numero_documento,
                            chave_acesso, data_emissao, cnpj_emissor, nome_emissor,
                            cnpj_destinatario, valor_descontos, valor_frete,
                            valor_acrescimos, valor_total_documento, categoria_sugerida,
                            status_aprovacao, alertas_json, itens_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            reg["hash_arquivo"],
                            reg["nome_arquivo"],
                            reg["tipo_documento"],
                            reg["numero_documento"],
                            reg["chave_acesso"],
                            str(reg["data_emissao"]) if reg["data_emissao"] else None,
                            reg["cnpj_emissor"],
                            reg["nome_emissor"],
                            reg["cnpj_destinatario"],
                            reg["valor_descontos"],
                            reg["valor_frete"],
                            reg["valor_acrescimos"],
                            reg["valor_total_documento"],
                            reg["categoria_sugerida"],
                            reg["status_aprovacao"],
                            json.dumps(reg["alertas"], ensure_ascii=False),
                            json.dumps(reg["itens"], ensure_ascii=False),
                        ),
                    )
                    salvos += 1
                except sqlite3.IntegrityError:
                    continue
        return salvos

    def excluir_documento(self, doc_id: int) -> bool:
        """Remove um registro do banco de dados pelo ID."""
        with self._conectar() as conn:
            cursor = conn.execute(
                "DELETE FROM documentos_fiscais WHERE id = ?",
                (int(doc_id),),
            )
            return cursor.rowcount > 0

    def obter_bytes_banco(self) -> bytes:
        """Retorna o arquivo .db bruto para backup."""
        if self.db_path.exists():
            return self.db_path.read_bytes()
        return b""

    def listar_todos(self) -> pd.DataFrame:
        with self._conectar() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    id, criado_em, nome_arquivo, status_aprovacao, tipo_documento,
                    numero_documento, data_emissao, cnpj_emissor, nome_emissor,
                    valor_descontos, valor_frete, valor_acrescimos,
                    valor_total_documento, categoria_sugerida, alertas_json
                FROM documentos_fiscais
                ORDER BY id DESC
                """,
                conn,
            )

    def listar_para_exportacao_excel(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        with self._conectar() as conn:
            df_completo = pd.read_sql_query(
                """
                SELECT
                    id, criado_em, nome_arquivo, status_aprovacao, tipo_documento,
                    numero_documento, chave_acesso, data_emissao, cnpj_emissor,
                    nome_emissor, cnpj_destinatario, valor_descontos, valor_frete,
                    valor_acrescimos, valor_total_documento, categoria_sugerida,
                    alertas_json, itens_json
                FROM documentos_fiscais
                ORDER BY id DESC
                """,
                conn,
            )

        if df_completo.empty:
            return pd.DataFrame(), pd.DataFrame()

        df_resumo = df_completo.drop(columns=["itens_json"]).copy()

        linhas_itens: List[Dict[str, Any]] = []
        for _, row in df_completo.iterrows():
            try:
                itens = json.loads(row["itens_json"] or "[]")
            except json.JSONDecodeError:
                itens = []

            for idx, item in enumerate(itens, start=1):
                linhas_itens.append({
                    "documento_id": row["id"],
                    "numero_documento": row["numero_documento"],
                    "data_emissao": row["data_emissao"],
                    "cnpj_emissor": row["cnpj_emissor"],
                    "nome_emissor": row["nome_emissor"],
                    "item_seq": idx,
                    "descricao": item.get("descricao", ""),
                    "quantidade": item.get("quantidade", 1.0),
                    "valor_unitario": item.get("valor_unitario", 0.0),
                    "valor_total_item": item.get("valor_total", 0.0),
                })

        df_itens = pd.DataFrame(linhas_itens)
        return df_resumo, df_itens