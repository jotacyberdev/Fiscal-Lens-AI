# 🧾 Fiscal-Lens-AI

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini%20API-Multimodal%20%26%20Text--to--SQL-4285F4?style=for-the-badge&logo=googlegemini&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

> **Plataforma corporativa de extração documental auditada (IDP), controle de acesso por cargo (RBAC) e Business Intelligence Conversacional (Text-to-SQL) potencializada por IA Generativa.**

---

## 🎯 Visão Geral

O **Fiscal-Lens-AI** transforma documentos fiscais não estruturados (`NF-e`, `NFS-e`, `NFC-e`, recibos e boletos em PDF ou imagem) em dados financeiros auditados e consultáveis em linguagem natural. Em vez de um simples "chat com PDF" sujeito a alucinações matemáticas, o sistema aplica um pipeline estruturado: **Ingestão Multimodal $\rightarrow$ Auditoria Determinística $\rightarrow$ Persistência Relacional com RBAC $\rightarrow$ BI Conversacional**.

---

## ✨ Principais Funcionalidades

* **📄 Extração Multimodal em Lote (IDP):** Leitura simultânea de arquivos `PDF`, `PNG`, `JPG` e `JPEG` utilizando a **Google Gemini API** com saída tipada via **Pydantic** (`Structured Outputs`).
* **🛡️ Motor de Auditoria e Compliance:**
  * Conferência matemática automática ($\text{Itens} + \text{Frete} + \text{Acréscimos} - \text{Descontos} = \text{Valor Total}$).
  * Validação de dígitos verificadores de **CNPJ** (emissor e destinatário) e detecção de divergências cadastrais.
  * **Trava Anti-Duplicidade:** Assinatura criptográfica do arquivo (`SHA-256`) combinada com verificação lógica no banco (CNPJ + Número do Documento + Valor).
* **🔐 Controle de Acesso Baseado em Cargo (RBAC):**
  * **Admin / Financeiro:** Visão irrestrita de todas as categorias, exportação completa, backup do banco `.db` e gestão/exclusão de registros.
  * **Operacional / TI:** Escopo isolado automaticamente (interface, dashboard, Excel e consultas SQL) para despesas operacionais (*Software, Transporte, Material de Escritório e Utilidades*).
* **💬 Analista IA — BI Conversacional (Text-to-SQL Auditável):**
  * Traduz perguntas em português para consultas `SELECT` no SQLite em tempo real, respeitando a política RBAC do usuário logado.
  * **Camada de Segurança SQL:** Validação estrita somente leitura com bloqueio contra comandos destrutivos (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`) e exibição transparente da query auditada.
  * Geração automática de tabelas e gráficos de barras conforme o tipo de resposta.
* **🔍 Revisão Split-Screen & Exportação Contábil:** Conferência lado a lado entre o documento original e os dados extraídos, dashboard executivo com KPIs e exportação em Excel (`.xlsx`) de duas abas (*Resumo das Notas* e *Itens Detalhados*).

---

## 🏗️ Arquitetura do Projeto

```text
Fiscal-Lens-AI/
├── app/
│   ├── schemas/
│   │   └── documento.py       # Modelos de dados e tipagem estrita (Pydantic v2)
│   └── services/
│       ├── extractor.py       # Extração multimodal com Google Gemini API
│       ├── validator.py       # Regras de negócio, cálculo de CNPJ e auditoria matemática
│       ├── storage.py         # Persistência SQLite, hash SHA-256, CRUD e exportação Excel
│       └── bi_agent.py        # Agente Text-to-SQL com validação somente leitura e filtro RBAC
├── streamlit_app.py           # Interface web, login RBAC, split-screen, dashboard e chat BI
├── main.py                    # Ponto de entrada alternativo CLI
├── requirements.txt           # Dependências do projeto
└── .gitignore                 # Proteção de credenciais (.env) e bancos locais (*.db)
