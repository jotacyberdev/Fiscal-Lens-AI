# 🧾 Fiscal-Lens-AI

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini%20API-Multimodal-4285F4?style=for-the-badge&logo=googlegemini&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

> **Plataforma inteligente de extração, auditoria e análise financeira de documentos fiscais (PDF e Imagens) potencializada por IA Generativa Multimodal.**

---

## 🎯 Sobre o Projeto

O **Fiscal-Lens-AI** elimina a digitação manual e reduz falhas de conformidade no lançamento de notas fiscais (`NF-e`, `NFS-e`, `NFC-e`), recibos e boletos. O sistema combina a leitura visual da **Google Gemini API** com regras determinísticas em Python para extrair dados estruturados, auditar cálculos matemáticos, detectar fraudes/duplicidades e gerar dashboards executivos prontos para exportação contábil.

---

## ✨ Principais Funcionalidades

* **📄 Leitura Multimodal em Lote:** Processamento simultâneo de arquivos `PDF`, `PNG`, `JPG` e `JPEG` com extração estruturada via **Pydantic** (`Structured Outputs`).
* **🛡️ Motor de Auditoria e Compliance:**
  * Validação matemática automática (soma dos itens $+$ frete $+$ acréscimos $-$ descontos $=$ valor total).
  * Verificação de dígitos verificadores de **CNPJ** (emissor e destinatário) e alerta de divergência cadastral.
  * **Bloqueio de Duplicidade em Duas Camadas:** Assinatura criptográfica do arquivo (`SHA-256`) e cruzamento lógico no banco de dados (CNPJ + Número do Documento + Valor).
* **🔍 Revisão Split-Screen (Lado a Lado):** Visualizador integrado do PDF/imagem original ao lado de formulário editável para conferência humana antes da gravação.
* **📊 Dashboard Financeiro & BI:** Indicadores executivos (Total Processado, Ticket Médio, Taxa de Aprovação Direta) e gráficos dinâmicos por **Categoria Contábil** e **Top 10 Fornecedores**.
* **📥 Exportação Contábil & Backup:** Geração de planilhas Excel (`.xlsx`) formatadas em duas abas (*Resumo das Notas* e *Itens Detalhados*), além de backup direto do banco SQLite (`.db`).
* **🔐 Controle de Acesso:** Autenticação integrada compatível com variáveis de ambiente locais (`.env`) e `st.secrets` em nuvem.

---

## 🏗️ Arquitetura do Projeto

```text
Fiscal-Lens-AI/
├── app/
│   ├── schemas/
│   │   └── documento.py       # Modelos de dados e tipagem estrita (Pydantic v2)
│   └── services/
│       ├── extractor.py       # Integração multimodal com Google Gemini API
│       ├── validator.py       # Regras de negócio, cálculo de CNPJ e auditoria matemática
│       └── storage.py         # Persistência SQLite, controle de hash e exportação Excel
├── streamlit_app.py           # Interface web, autenticação, split-screen e dashboard
├── main.py                    # Ponto de entrada alternativo CLI
├── requirements.txt           # Dependências do projeto
└── .gitignore                 # Proteção de credenciais (.env) e bancos locais (*.db)
