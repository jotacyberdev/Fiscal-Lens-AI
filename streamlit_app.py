import io
import os
import tempfile
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.services.bi_agent import AnalistaBIFiscal
from app.services.extractor import ExtratorDocumentos
from app.services.storage import RepositorioNotas

load_dotenv()

st.set_page_config(
    page_title="Fiscal-Lens-AI • Auditoria & BI",
    page_icon="🧾",
    layout="wide",
)

PERFIS_RBAC = {
    "Admin / Financeiro": {
        "secret_key": "APP_PASSWORD_ADMIN",
        "fallback_pwd": "admin123",
        "categorias": None,  # Acesso irrestrito
        "pode_excluir": True,
        "descricao": "Acesso total a todas as categorias, backup do banco e exclusão de registros.",
    },
    "Operacional / TI": {
        "secret_key": "APP_PASSWORD_OPERACIONAL",
        "fallback_pwd": "oper123",
        "categorias": ["Software", "Transporte", "Material de Escritório", "Utilidades"],
        "pode_excluir": False,
        "descricao": "Acesso restrito a despesas operacionais (Software, Transporte, Escritório, Utilidades).",
    },
}


def obter_segredo(chave: str, padrao: str = "") -> str:
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:
        pass
    return os.getenv(chave, padrao)


def verificar_autenticacao() -> bool:
    if st.session_state.get("autenticado", False):
        return True

    col_esq, col_centro, col_dir = st.columns([1, 1.35, 1])
    with col_centro:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔐 Fiscal-Lens-AI • Login Corporativo")
        st.caption("Controle de Acesso Baseado em Cargo (RBAC)")

        with st.form("form_login"):
            perfil_escolhido = st.selectbox("Perfil de Acesso", options=list(PERFIS_RBAC.keys()))
            st.info(PERFIS_RBAC[perfil_escolhido]["descricao"])
            senha_digitada = st.text_input("Senha do Perfil", type="password")
            entrar = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)

            if entrar:
                cfg = PERFIS_RBAC[perfil_escolhido]
                senha_correta = obter_segredo(cfg["secret_key"], cfg["fallback_pwd"])
                if senha_digitada == senha_correta:
                    st.session_state.autenticado = True
                    st.session_state.perfil_usuario = perfil_escolhido
                    st.session_state.historico_chat_bi = []
                    st.rerun()
                else:
                    st.error("Senha incorreta para o perfil selecionado.")

    return False


if not verificar_autenticacao():
    st.stop()

perfil_atual = st.session_state.get("perfil_usuario", "Admin / Financeiro")
regras_perfil = PERFIS_RBAC[perfil_atual]

if "lote_processado" not in st.session_state:
    st.session_state.lote_processado = []
if "historico_chat_bi" not in st.session_state:
    st.session_state.historico_chat_bi = []

repo = RepositorioNotas()

# --- BARRA LATERAL (CONFIGURAÇÕES E RBAC ATIVO) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    st.success(f"👤 **Perfil:** {perfil_atual}")
    if regras_perfil["categorias"]:
        st.caption(f"Escopo RBAC: {', '.join(regras_perfil['categorias'])}")
    else:
        st.caption("Escopo RBAC: Acesso Irrestrito")

    api_key_env = obter_segredo("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "Gemini API Key",
        value=api_key_env,
        type="password",
        help="Lida automaticamente do .env ou Secrets.",
    )
    cnpj_empresa = st.text_input(
        "CNPJ da Sua Empresa (Opcional)",
        placeholder="Ex: 12345678000199",
    )
    modelo_ia = st.selectbox(
        "Modelo Gemini",
        options=["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
    )
    st.divider()
    if st.button("🔒 Trocar Perfil / Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.historico_chat_bi = []
        st.rerun()
    st.caption("v2.0 • IDP + RBAC + BI Conversacional")

st.title("🧾 Fiscal-Lens-AI • Inteligência Documental & BI")
st.markdown("Extração multimodal auditada, controle de acesso por cargo (RBAC) e análise financeira em linguagem natural.")

aba_processar, aba_historico, aba_bi_chat = st.tabs([
    "📤 Processar & Revisar Lote",
    "🗄️ Dashboard & Banco de Dados",
    "💬 Analista IA (BI Conversacional)",
])

# ==============================================================================
# ABA 1: UPLOAD, EXTRAÇÃO E REVISÃO LADO A LADO
# ==============================================================================
with aba_processar:
    arquivos = st.file_uploader(
        "Arraste e solte seus documentos aqui",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if st.button("🚀 Extrair e Validar Documentos", type="primary", disabled=not arquivos):
        if not api_key_input:
            st.error("Configure sua GEMINI_API_KEY na barra lateral ou no arquivo .env.")
        else:
            extrator = ExtratorDocumentos(api_key=api_key_input, model_name=modelo_ia)
            resultados_temp = []
            barra = st.progress(0, text="Iniciando processamento...")

            for idx, arquivo in enumerate(arquivos):
                barra.progress((idx + 1) / len(arquivos), text=f"Lendo {arquivo.name}...")
                conteudo_bytes = arquivo.getvalue()
                sufixo = Path(arquivo.name).suffix.lower()

                with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
                    tmp.write(conteudo_bytes)
                    caminho_tmp = Path(tmp.name)

                try:
                    res = extrator.processar_arquivo(
                        caminho_arquivo=caminho_tmp,
                        cnpj_empresa_cliente=cnpj_empresa or None,
                    )

                    alertas = list(res.alertas)
                    if repo.arquivo_ja_processado(res.hash_arquivo):
                        alertas.insert(0, "DUPLICIDADE: Este exato arquivo já foi salvo anteriormente.")
                    elif repo.nota_duplicada(
                        res.dados.cnpj_emissor,
                        res.dados.numero_documento,
                        res.dados.valor_total_documento,
                    ):
                        alertas.insert(0, "DUPLICIDADE: Nota com mesmo CNPJ, número e valor já existe no banco.")

                    aprovado = len(alertas) == 0
                    dados_dict = res.dados.model_dump(mode="json")

                    resultados_temp.append({
                        "aprovar": aprovado,
                        "status": "✅ Aprovado" if aprovado else "⚠️ Revisar",
                        "nome_arquivo": arquivo.name,
                        "tipo_documento": dados_dict["tipo_documento"],
                        "numero_documento": dados_dict["numero_documento"] or "",
                        "data_emissao": dados_dict["data_emissao"] or "",
                        "cnpj_emissor": dados_dict["cnpj_emissor"] or "",
                        "nome_emissor": dados_dict["nome_emissor"],
                        "valor_total_documento": float(dados_dict["valor_total_documento"]),
                        "categoria_sugerida": dados_dict["categoria_sugerida"],
                        "alertas_texto": " | ".join(alertas) if alertas else "Nenhum alerta",
                        "_arquivo_bytes": conteudo_bytes,
                        "_extensao": sufixo,
                        "_hash_arquivo": res.hash_arquivo,
                        "_chave_acesso": dados_dict["chave_acesso"],
                        "_cnpj_destinatario": dados_dict["cnpj_destinatario"],
                        "_valor_descontos": dados_dict["valor_descontos"],
                        "_valor_frete": dados_dict["valor_frete"],
                        "_valor_acrescimos": dados_dict["valor_acrescimos"],
                        "_alertas_lista": alertas,
                        "_itens_lista": dados_dict["itens"],
                    })
                except Exception as e:
                    st.error(f"Erro ao processar '{arquivo.name}': {e}")
                finally:
                    if caminho_tmp.exists():
                        caminho_tmp.unlink()

            barra.empty()
            st.session_state.lote_processado = resultados_temp

    if st.session_state.lote_processado:
        st.divider()
        lote = st.session_state.lote_processado
        df_lote = pd.DataFrame(lote)

        total_docs = len(df_lote)
        qtd_aprovados = int(df_lote["aprovar"].sum())
        qtd_revisao = total_docs - qtd_aprovados
        soma_valores = df_lote["valor_total_documento"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Documentos Lidos", total_docs)
        col2.metric("Aprovados Direto", qtd_aprovados)
        col3.metric("Com Alertas", qtd_revisao)
        col4.metric("Valor Total Lote", f"R$ {soma_valores:,.2f}")

        st.subheader("🔍 Conferência Lado a Lado (Documento vs. Dados Extraídos)")
        opcoes_docs = [
            f"{i + 1}. {item['status']} — {item['nome_arquivo']} ({item['nome_emissor']})"
            for i, item in enumerate(lote)
        ]
        indice_selecionado = st.selectbox(
            "Selecione um documento para conferir o original e os itens:",
            options=range(len(lote)),
            format_func=lambda idx: opcoes_docs[idx],
        )

        doc_atual = lote[indice_selecionado]
        col_doc, col_form = st.columns([1.1, 1], gap="large")

        with col_doc:
            st.markdown(f"**Documento Original:** `{doc_atual['nome_arquivo']}`")
            if doc_atual["_extensao"] == ".pdf":
                st.pdf(doc_atual["_arquivo_bytes"], height=560)
            else:
                st.image(doc_atual["_arquivo_bytes"], use_container_width=True)

        with col_form:
            if doc_atual["_alertas_lista"]:
                for alerta in doc_atual["_alertas_lista"]:
                    st.warning(alerta)
            else:
                st.success("Nenhum alerta encontrado nas validações de CNPJ e soma.")

            with st.form(key=f"form_edicao_{indice_selecionado}"):
                c1, c2 = st.columns(2)
                tipos_padrao = ["NFe", "NFSe", "NFCe", "Recibo", "Boleto", "Outro"]
                idx_tipo = tipos_padrao.index(doc_atual["tipo_documento"]) if doc_atual["tipo_documento"] in tipos_padrao else 5
                novo_tipo = c1.selectbox("Tipo Documento", tipos_padrao, index=idx_tipo)
                novo_numero = c2.text_input("Número Documento", value=doc_atual["numero_documento"])

                c3, c4 = st.columns(2)
                nova_data = c3.text_input("Data Emissão (AAAA-MM-DD)", value=doc_atual["data_emissao"])
                novo_cnpj = c4.text_input("CNPJ Emissor", value=doc_atual["cnpj_emissor"])

                novo_emissor = st.text_input("Fornecedor / Emissor", value=doc_atual["nome_emissor"])

                c5, c6 = st.columns(2)
                novo_valor = c5.number_input(
                    "Valor Total (R$)",
                    value=float(doc_atual["valor_total_documento"]),
                    step=0.01,
                    format="%.2f",
                )
                categorias_padrao = [
                    "Alimentação",
                    "Transporte",
                    "Software",
                    "Material de Escritório",
                    "Serviços Terceiros",
                    "Utilidades",
                    "Outros",
                ]
                idx_cat = categorias_padrao.index(doc_atual["categoria_sugerida"]) if doc_atual["categoria_sugerida"] in categorias_padrao else 6
                nova_categoria = c6.selectbox("Categoria", categorias_padrao, index=idx_cat)

                novo_aprovar = st.checkbox("Marcar documento para salvar no banco", value=doc_atual["aprovar"])

                if st.form_submit_button("✅ Aplicar Correção neste Documento", use_container_width=True):
                    st.session_state.lote_processado[indice_selecionado].update({
                        "tipo_documento": novo_tipo,
                        "numero_documento": novo_numero,
                        "data_emissao": nova_data,
                        "cnpj_emissor": novo_cnpj,
                        "nome_emissor": novo_emissor,
                        "valor_total_documento": float(novo_valor),
                        "categoria_sugerida": nova_categoria,
                        "aprovar": novo_aprovar,
                        "status": "✅ Revisado" if novo_aprovar else "⚠️ Revisar",
                    })
                    st.rerun()

            st.markdown("**Itens / Serviços Extraídos:**")
            if doc_atual["_itens_lista"]:
                st.dataframe(pd.DataFrame(doc_atual["_itens_lista"]), use_container_width=True, hide_index=True)
            else:
                st.caption("Nenhum item discriminado individualmente neste documento.")

        st.divider()
        st.subheader("📋 Resumo Geral do Lote")
        colunas_visiveis = [
            "aprovar", "status", "nome_arquivo", "tipo_documento", "numero_documento",
            "data_emissao", "cnpj_emissor", "nome_emissor", "valor_total_documento",
            "categoria_sugerida", "alertas_texto",
        ]

        df_editado = st.data_editor(
            pd.DataFrame(st.session_state.lote_processado)[colunas_visiveis],
            use_container_width=True,
            hide_index=True,
            column_config={
                "aprovar": st.column_config.CheckboxColumn("Salvar?", default=True),
                "status": st.column_config.TextColumn("Status", disabled=True),
                "nome_arquivo": st.column_config.TextColumn("Arquivo", disabled=True),
                "tipo_documento": st.column_config.TextColumn("Tipo"),
                "numero_documento": st.column_config.TextColumn("Nº Doc"),
                "data_emissao": st.column_config.TextColumn("Data"),
                "cnpj_emissor": st.column_config.TextColumn("CNPJ Emissor"),
                "nome_emissor": st.column_config.TextColumn("Fornecedor"),
                "valor_total_documento": st.column_config.NumberColumn("Valor Total (R$)", format="%.2f"),
                "categoria_sugerida": st.column_config.TextColumn("Categoria"),
                "alertas_texto": st.column_config.TextColumn("Alertas", disabled=True),
            },
        )

        col_btn1, col_btn2 = st.columns([1.5, 4])
        with col_btn1:
            if st.button("💾 Salvar Marcados no Banco", type="primary"):
                registros_para_salvar = []
                for idx, row in df_editado.iterrows():
                    if row["aprovar"]:
                        original = st.session_state.lote_processado[idx]
                        registros_para_salvar.append({
                            "hash_arquivo": original["_hash_arquivo"],
                            "nome_arquivo": row["nome_arquivo"],
                            "tipo_documento": row["tipo_documento"],
                            "numero_documento": row["numero_documento"],
                            "chave_acesso": original["_chave_acesso"],
                            "data_emissao": row["data_emissao"],
                            "cnpj_emissor": row["cnpj_emissor"],
                            "nome_emissor": row["nome_emissor"],
                            "cnpj_destinatario": original["_cnpj_destinatario"],
                            "valor_descontos": original["_valor_descontos"],
                            "valor_frete": original["_valor_frete"],
                            "valor_acrescimos": original["_valor_acrescimos"],
                            "valor_total_documento": float(row["valor_total_documento"]),
                            "categoria_sugerida": row["categoria_sugerida"],
                            "status_aprovacao": "Aprovado Manualmente" if original["_alertas_lista"] else "Aprovado Auto",
                            "alertas": original["_alertas_lista"],
                            "itens": original["_itens_lista"],
                        })

                qtd_salva = repo.salvar_lote(registros_para_salvar)
                st.success(f"{qtd_salva} documento(s) gravado(s) com sucesso!")
                st.session_state.lote_processado = []
                st.rerun()

        with col_btn2:
            if st.button("🗑️ Limpar Tela"):
                st.session_state.lote_processado = []
                st.rerun()

# ==============================================================================
# ABA 2: DASHBOARD FINANCEIRO (FILTRADO POR RBAC) E EXPORTAÇÃO
# ==============================================================================
with aba_historico:
    df_resumo_bruto, df_itens = repo.listar_para_exportacao_excel()

    # Aplica filtro de segurança RBAC antes de exibir qualquer número
    if not df_resumo_bruto.empty and regras_perfil["categorias"]:
        df_resumo = df_resumo_bruto[
            df_resumo_bruto["categoria_sugerida"].isin(regras_perfil["categorias"])
        ].copy()
        st.info(f"🔒 Visão filtrada pela política RBAC do perfil **{perfil_atual}**.")
    else:
        df_resumo = df_resumo_bruto.copy()

    if df_resumo.empty:
        st.info("Nenhum documento disponível para o seu perfil no banco de dados ainda.")
    else:
        st.subheader("📊 Painel Financeiro e Auditoria")
        f1, f2 = st.columns(2)
        categorias_disponiveis = sorted(df_resumo["categoria_sugerida"].dropna().unique().tolist())
        tipos_disponiveis = sorted(df_resumo["tipo_documento"].dropna().unique().tolist())

        cats_selecionadas = f1.multiselect("Filtrar por Categoria", options=categorias_disponiveis, default=categorias_disponiveis)
        tipos_selecionados = f2.multiselect("Filtrar por Tipo de Documento", options=tipos_disponiveis, default=tipos_disponiveis)

        df_filtrado = df_resumo[
            df_resumo["categoria_sugerida"].isin(cats_selecionadas)
            & df_resumo["tipo_documento"].isin(tipos_selecionados)
        ].copy()

        total_gasto = df_filtrado["valor_total_documento"].sum()
        qtd_notas = len(df_filtrado)
        ticket_medio = total_gasto / qtd_notas if qtd_notas > 0 else 0.0
        qtd_auto = int((df_filtrado["status_aprovacao"] == "Aprovado Auto").sum())
        taxa_auto = (qtd_auto / qtd_notas * 100) if qtd_notas > 0 else 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Processado", f"R$ {total_gasto:,.2f}")
        k2.metric("Notas Aprovadas", qtd_notas)
        k3.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}")
        k4.metric("Aprovação Direta (IA)", f"{taxa_auto:.0f}%")

        st.divider()

        g1, g2 = st.columns(2, gap="large")
        with g1:
            st.markdown("**💰 Gastos por Categoria (R$)**")
            if not df_filtrado.empty:
                st.bar_chart(
                    df_filtrado.groupby("categoria_sugerida")["valor_total_documento"].sum().sort_values(ascending=False),
                    horizontal=True,
                    color="#2563EB",
                )
        with g2:
            st.markdown("**🏢 Top 10 Fornecedores por Volume (R$)**")
            if not df_filtrado.empty:
                st.bar_chart(
                    df_filtrado.groupby("nome_emissor")["valor_total_documento"].sum().sort_values(ascending=False).head(10),
                    horizontal=True,
                    color="#10B981",
                )

        st.divider()
        st.subheader("📑 Registros Salvos")
        tab_res, tab_it = st.tabs(["📄 Resumo das Notas", "📦 Itens Detalhados"])

        with tab_res:
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

        with tab_it:
            if df_itens.empty:
                st.info("Nenhum item individual registrado nas notas salvas.")
            else:
                ids_filtrados = set(df_filtrado["id"].tolist())
                st.dataframe(df_itens[df_itens["documento_id"].isin(ids_filtrados)], use_container_width=True, hide_index=True)

        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Resumo_Notas")
            if not df_itens.empty:
                ids_filtrados = set(df_filtrado["id"].tolist())
                df_itens[df_itens["documento_id"].isin(ids_filtrados)].to_excel(writer, index=False, sheet_name="Itens_Detalhados")
            else:
                pd.DataFrame({"Aviso": ["Nenhum item detalhado extraído"]}).to_excel(writer, index=False, sheet_name="Itens_Detalhados")

        col_exp1, col_exp2 = st.columns([2, 2])
        with col_exp1:
            st.download_button(
                label="📥 Baixar Planilha Filtrada (2 Abas .xlsx)",
                data=buffer_excel.getvalue(),
                file_name=f"relatorio_fiscal_{perfil_atual.split()[0].lower()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )

        if regras_perfil["pode_excluir"]:
            with col_exp2:
                st.download_button(
                    label="🗄️ Baixar Backup Completo do Banco (.db)",
                    data=repo.obter_bytes_banco(),
                    file_name="backup_notas_fiscais.db",
                    mime="application/octet-stream",
                    use_container_width=True,
                )

            st.divider()
            with st.expander("🗑️ Gerenciar / Excluir Registro Salvo (Exclusivo Admin)"):
                opcoes_exclusao = {
                    int(row["id"]): f"ID #{row['id']} — {row['nome_emissor']} | Doc: {row['numero_documento'] or 'S/N'} | R$ {row['valor_total_documento']:,.2f}"
                    for _, row in df_resumo_bruto.iterrows()
                }
                id_para_excluir = st.selectbox(
                    "Selecione o registro que deseja remover:",
                    options=list(opcoes_exclusao.keys()),
                    format_func=lambda x: opcoes_exclusao[x],
                )
                if st.button("❌ Excluir Registro Selecionado"):
                    if repo.excluir_documento(id_para_excluir):
                        st.success(f"Registro ID #{id_para_excluir} removido!")
                        st.rerun()

# ==============================================================================
# ABA 3: ANALISTA IA - BI CONVERSACIONAL (TEXT-TO-SQL AUDITÁVEL COM RBAC)
# ==============================================================================
with aba_bi_chat:
    st.subheader("💬 BI Conversacional • Pergunte aos Seus Dados Fiscais")
    st.caption(
        f"Faça perguntas em português sobre o banco SQLite. As consultas SQL são geradas automaticamente "
        f"em modo somente leitura respeitando as permissões do perfil **{perfil_atual}**."
    )

    sugestoes = [
        "Qual é o valor total gasto por categoria?",
        "Quais são os 5 maiores fornecedores em volume financeiro?",
        "Quantas notas foram aprovadas manualmente versus automaticamente?",
        "Mostre todas as notas com valor acima de R$ 500.",
    ]
    cols_sug = st.columns(len(sugestoes))
    pergunta_sugerida = None
    for idx, sug in enumerate(sugestoes):
        if cols_sug[idx].button(sug, use_container_width=True, key=f"sug_bi_{idx}"):
            pergunta_sugerida = sug

    # Renderiza histórico da conversa de BI
    for msg in st.session_state.historico_chat_bi:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sql" in msg:
                with st.expander("🔍 Ver Query SQL Auditada (Somente Leitura)"):
                    st.code(msg["sql"], language="sql")
            if "dados" in msg and isinstance(msg["dados"], pd.DataFrame) and not msg["dados"].empty:
                df_msg = msg["dados"]
                st.dataframe(df_msg, use_container_width=True, hide_index=True)
                if msg.get("visualizacao") == "barras" and len(df_msg.columns) >= 2 and len(df_msg) > 1:
                    col_cat, col_val = df_msg.columns[0], df_msg.columns[1]
                    if pd.api.types.is_numeric_dtype(df_msg[col_val]):
                        st.bar_chart(df_msg.set_index(col_cat)[col_val], horizontal=True)

    pergunta_digitada = st.chat_input("Ex: Quanto gastamos no total e qual foi o maior fornecedor?")
    pergunta_final = pergunta_sugerida or pergunta_digitada

    if pergunta_final:
        if not api_key_input:
            st.error("Configure sua GEMINI_API_KEY na barra lateral.")
        else:
            st.session_state.historico_chat_bi.append({"role": "user", "content": pergunta_final})
            with st.chat_message("user"):
                st.markdown(pergunta_final)

            with st.chat_message("assistant"):
                with st.spinner("Gerando consulta SQL segura e analisando banco..."):
                    try:
                        analista = AnalistaBIFiscal(api_key=api_key_input, model_name=modelo_ia)
                        res_bi = analista.responder_pergunta(
                            pergunta=pergunta_final,
                            cargo=perfil_atual,
                            categorias_permitidas=regras_perfil["categorias"],
                        )
                        st.markdown(res_bi["explicacao"])
                        with st.expander("🔍 Ver Query SQL Auditada (Somente Leitura)"):
                            st.code(res_bi["sql"], language="sql")

                        df_res = res_bi["dados"]
                        if df_res.empty:
                            st.warning("Nenhum registro encontrado para essa consulta dentro do seu escopo de acesso.")
                        else:
                            st.dataframe(df_res, use_container_width=True, hide_index=True)
                            if res_bi["visualizacao"] == "barras" and len(df_res.columns) >= 2 and len(df_res) > 1:
                                col_cat, col_val = df_res.columns[0], df_res.columns[1]
                                if pd.api.types.is_numeric_dtype(df_res[col_val]):
                                    st.bar_chart(df_res.set_index(col_cat)[col_val], horizontal=True)

                        st.session_state.historico_chat_bi.append({
                            "role": "assistant",
                            "content": res_bi["explicacao"],
                            "sql": res_bi["sql"],
                            "dados": df_res,
                            "visualizacao": res_bi["visualizacao"],
                        })
                    except Exception as e:
                        erro_msg = f"Não foi possível executar a análise: {e}"
                        st.error(erro_msg)
                        st.session_state.historico_chat_bi.append({"role": "assistant", "content": erro_msg})