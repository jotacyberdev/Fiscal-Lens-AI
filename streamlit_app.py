import io
import os
import tempfile
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.services.extractor import ExtratorDocumentos
from app.services.storage import RepositorioNotas

load_dotenv()

st.set_page_config(
    page_title="Extrator & Validador Fiscal IA",
    page_icon="🧾",
    layout="wide",
)


def obter_segredo(chave: str, padrao: str = "") -> str:
    """Lê de st.secrets (quando publicado online) ou do .env / variáveis de ambiente."""
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:
        pass
    return os.getenv(chave, padrao)


def verificar_autenticacao() -> bool:
    """Bloqueia o acesso à aplicação até que a senha correta seja informada."""
    senha_correta = obter_segredo("APP_PASSWORD", "admin123")

    if st.session_state.get("autenticado", False):
        return True

    col_esq, col_centro, col_dir = st.columns([1, 1.3, 1])
    with col_centro:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔐 Acesso Restrito")
        st.caption("Extrator & Validador Inteligente de Documentos")

        with st.form("form_login"):
            senha_digitada = st.text_input("Senha de Acesso", type="password")
            entrar = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)

            if entrar:
                if senha_digitada == senha_correta:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta. Tente novamente.")

    return False


# Interrompe a renderização do restante da página se não estiver logado
if not verificar_autenticacao():
    st.stop()

if "lote_processado" not in st.session_state:
    st.session_state.lote_processado = []

repo = RepositorioNotas()

# --- BARRA LATERAL (CONFIGURAÇÕES) ---
with st.sidebar:
    st.header("⚙️ Configurações")
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
        help="Se preenchido, alerta caso a nota tenha sido emitida para outro CNPJ.",
    )
    modelo_ia = st.selectbox(
        "Modelo Gemini",
        options=["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
    )
    st.divider()
    if st.button("🔒 Sair / Bloquear Tela", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()
    st.caption("v1.3 • Login + Split-Screen + Dashboard + Gestão DB")

st.title("🧾 Extrator e Validador Inteligente de Documentos")
st.markdown("Faça upload de notas fiscais, recibos ou boletos (PDF, PNG, JPG) para extração automática e auditoria.")

aba_processar, aba_historico = st.tabs(["📤 Processar & Revisar Lote", "🗄️ Dashboard & Banco de Dados"])

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

    # --- PAINEL DE REVISÃO ---
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

        # --- VISUALIZADOR LADO A LADO ---
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
                df_itens_doc = pd.DataFrame(doc_atual["_itens_lista"])
                st.dataframe(df_itens_doc, use_container_width=True, hide_index=True)
            else:
                st.caption("Nenhum item discriminado individualmente neste documento.")

        # --- TABELA RESUMO DO LOTE E GRAVAÇÃO ---
        st.divider()
        st.subheader("📋 Resumo Geral do Lote")
        colunas_visiveis = [
            "aprovar",
            "status",
            "nome_arquivo",
            "tipo_documento",
            "numero_documento",
            "data_emissao",
            "cnpj_emissor",
            "nome_emissor",
            "valor_total_documento",
            "categoria_sugerida",
            "alertas_texto",
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
                st.success(f"{qtd_salva} documento(s) gravado(s) com sucesso no banco de dados!")
                st.session_state.lote_processado = []
                st.rerun()

        with col_btn2:
            if st.button("🗑️ Limpar Tela"):
                st.session_state.lote_processado = []
                st.rerun()

# ==============================================================================
# ABA 2: DASHBOARD FINANCEIRO, HISTÓRICO, EXCLUSÃO E EXPORTAÇÃO EXCEL
# ==============================================================================
with aba_historico:
    df_resumo, df_itens = repo.listar_para_exportacao_excel()

    if df_resumo.empty:
        st.info("Nenhum documento salvo no banco de dados ainda. Processe e salve notas na primeira aba para ver o dashboard.")
    else:
        # --- FILTROS DO DASHBOARD ---
        st.subheader("📊 Painel Financeiro e Auditoria")
        f1, f2 = st.columns(2)
        categorias_disponiveis = sorted(df_resumo["categoria_sugerida"].dropna().unique().tolist())
        tipos_disponiveis = sorted(df_resumo["tipo_documento"].dropna().unique().tolist())

        cats_selecionadas = f1.multiselect(
            "Filtrar por Categoria",
            options=categorias_disponiveis,
            default=categorias_disponiveis,
        )
        tipos_selecionados = f2.multiselect(
            "Filtrar por Tipo de Documento",
            options=tipos_disponiveis,
            default=tipos_disponiveis,
        )

        df_filtrado = df_resumo[
            df_resumo["categoria_sugerida"].isin(cats_selecionadas)
            & df_resumo["tipo_documento"].isin(tipos_selecionados)
        ].copy()

        # --- KPIs EXECUTIVOS ---
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

        # --- GRÁFICOS POR CATEGORIA E FORNECEDOR ---
        g1, g2 = st.columns(2, gap="large")

        with g1:
            st.markdown("**💰 Gastos por Categoria (R$)**")
            if not df_filtrado.empty:
                gastos_categoria = (
                    df_filtrado.groupby("categoria_sugerida")["valor_total_documento"]
                    .sum()
                    .sort_values(ascending=False)
                )
                st.bar_chart(gastos_categoria, horizontal=True, color="#2563EB")
            else:
                st.caption("Sem dados para os filtros selecionados.")

        with g2:
            st.markdown("**🏢 Top 10 Fornecedores por Volume (R$)**")
            if not df_filtrado.empty:
                gastos_fornecedor = (
                    df_filtrado.groupby("nome_emissor")["valor_total_documento"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                st.bar_chart(gastos_fornecedor, horizontal=True, color="#10B981")
            else:
                st.caption("Sem dados para os filtros selecionados.")

        st.divider()

        # --- TABELAS DETALHADAS ---
        st.subheader("📑 Registros Salvos")
        tab_res, tab_it = st.tabs(["📄 Resumo das Notas", "📦 Itens Detalhados"])

        with tab_res:
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

        with tab_it:
            if df_itens.empty:
                st.info("Nenhum item individual registrado nas notas salvas.")
            else:
                ids_filtrados = set(df_filtrado["id"].tolist())
                df_itens_filtrado = df_itens[df_itens["documento_id"].isin(ids_filtrados)]
                st.dataframe(df_itens_filtrado, use_container_width=True, hide_index=True)

        # --- EXPORTAÇÃO E BACKUP ---
        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Resumo_Notas")
            if not df_itens.empty:
                ids_filtrados = set(df_filtrado["id"].tolist())
                df_itens[df_itens["documento_id"].isin(ids_filtrados)].to_excel(
                    writer, index=False, sheet_name="Itens_Detalhados"
                )
            else:
                pd.DataFrame({"Aviso": ["Nenhum item detalhado extraído"]}).to_excel(
                    writer, index=False, sheet_name="Itens_Detalhados"
                )

        col_exp1, col_exp2 = st.columns([2, 2])
        with col_exp1:
            st.download_button(
                label="📥 Baixar Planilha Filtrada (2 Abas .xlsx)",
                data=buffer_excel.getvalue(),
                file_name="relatorio_fiscal_completo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )
        with col_exp2:
            st.download_button(
                label="🗄️ Baixar Backup do Banco (.db)",
                data=repo.obter_bytes_banco(),
                file_name="backup_notas_fiscais.db",
                mime="application/octet-stream",
                use_container_width=True,
            )

        # --- GERENCIAMENTO / EXCLUSÃO DE REGISTROS ---
        st.divider()
        with st.expander("🗑️ Gerenciar / Excluir Registro Salvo por Engano"):
            opcoes_exclusao = {
                int(row["id"]): f"ID #{row['id']} — {row['nome_emissor']} | Doc: {row['numero_documento'] or 'S/N'} | R$ {row['valor_total_documento']:,.2f} ({row['nome_arquivo']})"
                for _, row in df_resumo.iterrows()
            }
            id_para_excluir = st.selectbox(
                "Selecione o registro que deseja remover definitivamente do banco:",
                options=list(opcoes_exclusao.keys()),
                format_func=lambda x: opcoes_exclusao[x],
            )
            if st.button("❌ Excluir Registro Selecionado", type="secondary"):
                if repo.excluir_documento(id_para_excluir):
                    st.success(f"Registro ID #{id_para_excluir} removido com sucesso!")
                    st.rerun()