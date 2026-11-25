import json
from dotenv import load_dotenv
from app.services.extractor import ExtratorDocumentos

load_dotenv()


def main():
    extrator = ExtratorDocumentos(model_name="gemini-2.5-flash")

    caminho_teste = "tests/fixtures/nota_fiscal_exemplo.pdf"
    cnpj_cliente = "12345678000199"  # Opcional: CNPJ da empresa que está recebendo a nota

    print(f"Processando: {caminho_teste}...\n")
    resultado = extrator.processar_arquivo(
        caminho_arquivo=caminho_teste,
        cnpj_empresa_cliente=cnpj_cliente,
    )

    status = "APROVADO AUTOMATICAMENTE" if resultado.aprovado_automaticamente else "REQUER REVISÃO HUMANA"
    print(f"Status: {status}")
    print(f"SHA-256: {resultado.hash_arquivo}\n")

    if resultado.alertas:
        print("Alertas encontrados:")
        for alerta in resultado.alertas:
            print(f"  - [!] {alerta}")
        print()

    print("JSON Estruturado Extraído:")
    print(json.dumps(resultado.dados.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()