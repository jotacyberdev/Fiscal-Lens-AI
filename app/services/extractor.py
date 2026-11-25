import hashlib
import mimetypes
from pathlib import Path
from google import genai
from google.genai import types
from app.schemas.documento import DocumentoFiscal, ResultadoProcessamento
from app.services.validator import validar_documento


PROMPT_EXTRACAO = """
Você é um auditor contábil e especialista em documentos fiscais brasileiros (NF-e, NFS-e, NFC-e, recibos e boletos).
Analise o documento anexado e extraia todos os campos estruturados com precisão absoluta.

Regras obrigatórias:
1. Extraia apenas dígitos numéricos para CNPJs e chaves de acesso (remova pontos, barras e traços).
2. Converta valores monetários para float usando ponto como separador decimal.
3. Se houver tabela de produtos ou serviços, extraia cada linha separadamente na lista de itens.
4. Não invente dados ausentes; retorne null nos campos opcionais que não existirem no documento.
"""


class ExtratorDocumentos:
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-2.5-flash"):
        # Se api_key for None, o SDK lê automaticamente a variável de ambiente GEMINI_API_KEY
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.model_name = model_name

    @staticmethod
    def _gerar_hash(conteudo_bytes: bytes) -> str:
        return hashlib.sha256(conteudo_bytes).hexdigest()

    def processar_arquivo(
        self,
        caminho_arquivo: str | Path,
        cnpj_empresa_cliente: str | None = None,
    ) -> ResultadoProcessamento:
        path = Path(caminho_arquivo)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        conteudo_bytes = path.read_bytes()
        hash_arquivo = self._gerar_hash(conteudo_bytes)

        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            mime_type = "application/pdf" if path.suffix.lower() == ".pdf" else "image/jpeg"

        documento_part = types.Part.from_bytes(
            data=conteudo_bytes,
            mime_type=mime_type,
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[documento_part, PROMPT_EXTRACAO],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DocumentoFiscal,
                temperature=0.0,  # Zero criatividade para extração determinística
            ),
        )

        dados_extraidos: DocumentoFiscal = response.parsed
        alertas = validar_documento(
            doc=dados_extraidos,
            cnpj_empresa_cliente=cnpj_empresa_cliente,
        )

        return ResultadoProcessamento(
            hash_arquivo=hash_arquivo,
            aprovado_automaticamente=len(alertas) == 0,
            alertas=alertas,
            dados=dados_extraidos,
        )