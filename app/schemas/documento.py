from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field


class ItemNota(BaseModel):
    descricao: str = Field(description="Nome ou descrição do produto ou serviço")
    quantidade: float = Field(default=1.0, description="Quantidade do item")
    valor_unitario: float = Field(description="Preço unitário do item")
    valor_total: float = Field(description="Valor total da linha do item")


class DocumentoFiscal(BaseModel):
    tipo_documento: str = Field(
        description="Tipo do documento: NFe, NFSe, NFCe, Recibo, Boleto ou Outro"
    )
    numero_documento: Optional[str] = Field(
        None, description="Número da nota fiscal ou recibo"
    )
    chave_acesso: Optional[str] = Field(
        None, description="Chave de acesso de 44 dígitos numéricos, se presente"
    )
    data_emissao: Optional[date] = Field(
        None, description="Data de emissão no formato YYYY-MM-DD"
    )
    cnpj_emissor: Optional[str] = Field(
        None, description="CNPJ do fornecedor/emissor contendo apenas 14 números"
    )
    nome_emissor: str = Field(description="Razão social ou nome fantasia do emissor")
    cnpj_destinatario: Optional[str] = Field(
        None, description="CNPJ ou CPF do cliente/destinatário contendo apenas números"
    )
    itens: List[ItemNota] = Field(
        default_factory=list, description="Lista de itens ou serviços discriminados"
    )
    valor_descontos: float = Field(default=0.0, description="Valor total de descontos")
    valor_frete: float = Field(default=0.0, description="Valor total de frete/entrega")
    valor_acrescimos: float = Field(
        default=0.0, description="Outras despesas acessórias, juros ou multas"
    )
    valor_total_documento: float = Field(
        description="Valor líquido total cobrado no documento"
    )
    categoria_sugerida: str = Field(
        description="Categoria contábil sugerida: Alimentação, Transporte, Software, Material de Escritório, Serviços Terceiros, Utilidades ou Outros"
    )


class ResultadoProcessamento(BaseModel):
    hash_arquivo: str
    aprovado_automaticamente: bool
    alertas: List[str]
    dados: DocumentoFiscal