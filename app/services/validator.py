import re
from datetime import date, timedelta
from typing import List
from app.schemas.documento import DocumentoFiscal


def limpar_numeros(valor: str | None) -> str:
    if not valor:
        return ""
    return re.sub(r"\D", "", valor)


def validar_cnpj(cnpj: str | None) -> bool:
    """Valida os dígitos verificadores de um CNPJ brasileiro (Módulo 11)."""
    numeros = limpar_numeros(cnpj)

    if len(numeros) != 14 or len(set(numeros)) == 1:
        return False

    def calcular_digito(fatia: str, pesos: List[int]) -> str:
        soma = sum(int(digito) * peso for digito, peso in zip(fatia, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    digito_1 = calcular_digito(numeros[:12], pesos_1)
    digito_2 = calcular_digito(numeros[:12] + digito_1, pesos_2)

    return numeros[-2:] == digito_1 + digito_2


def validar_documento(
    doc: DocumentoFiscal,
    cnpj_empresa_cliente: str | None = None,
    tolerancia_centavos: float = 0.05,
) -> List[str]:
    """Roda regras determinísticas e retorna uma lista de alertas encontrados."""
    alertas: List[str] = []

    # 1. Validação do CNPJ do Emissor
    if not doc.cnpj_emissor:
        alertas.append("CNPJ do emissor não identificado no documento.")
    elif not validar_cnpj(doc.cnpj_emissor):
        alertas.append(f"CNPJ do emissor inválido (erro de OCR ou cadastro): {doc.cnpj_emissor}")

    # 2. Validação do CNPJ do Destinatário (se configurado)
    if cnpj_empresa_cliente and doc.cnpj_destinatario:
        cliente_limpo = limpar_numeros(cnpj_empresa_cliente)
        dest_limpo = limpar_numeros(doc.cnpj_destinatario)
        if len(dest_limpo) == 14 and dest_limpo != cliente_limpo:
            alertas.append(
                f"CNPJ destinatário ({dest_limpo}) difere da empresa ({cliente_limpo})."
            )

    # 3. Validação da Chave de Acesso (NFe/NFCe)
    if doc.chave_acesso:
        chave_limpa = limpar_numeros(doc.chave_acesso)
        if len(chave_limpa) != 44:
            alertas.append(f"Chave de acesso incompleta ({len(chave_limpa)} de 44 dígitos).")

    # 4. Prova Real Matemática dos Itens vs. Total
    if doc.itens:
        soma_itens = sum(item.valor_total for item in doc.itens)
        total_calculado = (
            soma_itens
            + doc.valor_frete
            + doc.valor_acrescimos
            - doc.valor_descontos
        )
        diferenca = abs(total_calculado - doc.valor_total_documento)

        if diferenca > tolerancia_centavos:
            alertas.append(
                f"Divergência matemática: soma calculada R$ {total_calculado:.2f} "
                f"vs. total do documento R$ {doc.valor_total_documento:.2f} "
                f"(diferença de R$ {diferenca:.2f})."
            )

        # Verifica consistência linha a linha (qtd * unitario == total_item)
        for idx, item in enumerate(doc.itens, start=1):
            esperado_item = item.quantidade * item.valor_unitario
            if abs(esperado_item - item.valor_total) > tolerancia_centavos:
                alertas.append(
                    f"Item {idx} ('{item.descricao}'): {item.quantidade} x "
                    f"R$ {item.valor_unitario:.2f} != R$ {item.valor_total:.2f}."
                )

    # 5. Validação de Data de Emissão
    if not doc.data_emissao:
        alertas.append("Data de emissão não encontrada.")
    else:
        hoje = date.today()
        if doc.data_emissao > hoje:
            alertas.append(f"Data de emissão futura detectada: {doc.data_emissao}.")
        elif doc.data_emissao < (hoje - timedelta(days=180)):
            alertas.append(f"Documento emitido há mais de 180 dias: {doc.data_emissao}.")

    return alertas