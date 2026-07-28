"""Meu Perfil — dados do avaliador usados nos PTAMs e apresentações."""
import streamlit as st

from core import db

st.title("👤 Meu Perfil")
st.caption("Seus dados aparecem nos PDFs de PTAM e na assinatura das avaliações.")

user_id = st.session_state.get("user_id")
user_email = st.session_state.get("user_email", "")

# Carrega do session_state (já carregado pelo roteador) ou do banco
perfil = st.session_state.get("perfil") or {}

if not perfil.get("creci"):
    st.warning(
        "**CRECI não preenchido.** Preencha seu registro para que os PTAMs gerados "
        "contenham sua assinatura e credencial.",
        icon="⚠️",
    )

st.markdown(f"**E-mail de acesso:** `{user_email}`")
st.divider()

with st.form("form_perfil"):
    st.subheader("Dados profissionais")
    nome = st.text_input("Nome completo *", value=perfil.get("nome", ""),
                         placeholder="Ex: João Silva Santos")
    titulo = st.text_input("Título / cargo", value=perfil.get("titulo", "Corretor de Imóveis"),
                            placeholder="Ex: Corretor de Imóveis · Avaliador")
    col1, col2 = st.columns(2)
    creci = col1.text_input("CRECI *", value=perfil.get("creci", ""),
                             placeholder="Ex: CRECI-SP 123.456-F")
    cnai = col2.text_input("CNAI (opcional)", value=perfil.get("cnai", ""),
                            placeholder="Cadastro Nacional de Avaliadores")

    st.subheader("Contato")
    col3, col4 = st.columns(2)
    telefone = col3.text_input("Telefone / WhatsApp",
                                value=perfil.get("telefone", "") or perfil.get("whatsapp", ""),
                                placeholder="+55 (11) 99999-9999")
    email_contato = col4.text_input("E-mail de contato",
                                    value=perfil.get("email_contato", ""),
                                    placeholder="contato@email.com")
    cidade_uf = st.text_input("Cidade/UF", value=perfil.get("cidade_uf", ""),
                               placeholder="Ex: Itatiba/SP")

    salvar = st.form_submit_button("💾 Salvar perfil", type="primary",
                                   use_container_width=True)

if salvar:
    if not nome.strip():
        st.error("Nome é obrigatório.")
    elif not creci.strip():
        st.error("CRECI é obrigatório.")
    else:
        novo = {
            "nome": nome.strip(),
            "titulo": titulo.strip() or "Corretor de Imóveis",
            "creci": creci.strip(),
            "cnai": cnai.strip(),
            "telefone": telefone.strip(),
            "whatsapp": telefone.strip(),
            "email_contato": email_contato.strip(),
            "cidade_uf": cidade_uf.strip(),
        }
        try:
            db.salvar_perfil(user_id, novo)
            # Atualiza o session_state para refletir imediatamente no app
            st.session_state["perfil"] = novo
            st.session_state["perfil_carregado"] = True
            st.success("Perfil salvo com sucesso!")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
