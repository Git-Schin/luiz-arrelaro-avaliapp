"""Auth multi-usuário via Supabase Auth (e-mail + senha)."""
from __future__ import annotations

import streamlit as st


def login(email: str, password: str) -> tuple[bool, str]:
    """Autentica. Retorna (sucesso, mensagem_erro)."""
    from core.supa import auth_client
    try:
        ac = auth_client()
        resp = ac.auth.sign_in_with_password({"email": email.strip(), "password": password})
        if resp.user:
            st.session_state["user_id"] = str(resp.user.id)
            st.session_state["user_email"] = resp.user.email
            # Força recarga do perfil na próxima visita ao roteador
            st.session_state.pop("perfil_carregado", None)
            st.session_state.pop("perfil", None)
            return True, ""
        return False, "Credenciais inválidas."
    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg or "invalid_credentials" in msg.lower():
            return False, "E-mail ou senha incorretos."
        return False, f"Erro ao autenticar: {msg[:120]}"


def registrar(email: str, password: str) -> tuple[bool, str]:
    """Cria conta nova. Retorna (sucesso, mensagem)."""
    from core.supa import auth_client
    try:
        ac = auth_client()
        resp = ac.auth.sign_up({"email": email.strip(), "password": password})
        if resp.user:
            return True, "Conta criada! Faça login para continuar."
        return False, "Não foi possível criar a conta."
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower() or "already been registered" in msg.lower():
            return False, "Este e-mail já está cadastrado."
        return False, f"Erro ao cadastrar: {msg[:120]}"


def logout() -> None:
    """Encerra a sessão limpando o session_state."""
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def require_login() -> None:
    """Bloqueia o app até autenticar. Chamar no roteador (app.py)."""
    if st.session_state.get("user_id"):
        return

    # Centraliza o formulário de login
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown(
            "<div style='text-align:center;padding:1.5rem 0 0.5rem;'>"
            "<span style='font-size:2rem;font-weight:700;color:#1B3A6B;'>Avali</span>"
            "<span style='font-size:2rem;font-weight:300;color:#10B981;'>App</span>"
            "<p style='color:#64748B;margin:0.25rem 0 1.5rem;font-size:0.95rem;'>"
            "Avaliação de imóveis com precisão e tecnologia</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        tab_login, tab_reg = st.tabs(["Entrar", "Criar conta"])

        with tab_login:
            email = st.text_input("E-mail", key="login_email",
                                  placeholder="seu@email.com")
            senha = st.text_input("Senha", type="password", key="login_senha")
            if st.button("Entrar", type="primary", use_container_width=True):
                if not email or not senha:
                    st.error("Preencha e-mail e senha.")
                else:
                    ok, msg = login(email, senha)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

        with tab_reg:
            r_email = st.text_input("E-mail", key="reg_email",
                                    placeholder="seu@email.com")
            r_senha = st.text_input("Senha (mín. 6 caracteres)", type="password",
                                    key="reg_senha")
            r_conf = st.text_input("Confirmar senha", type="password", key="reg_conf")
            if st.button("Criar conta", type="primary",
                         use_container_width=True, key="btn_registrar"):
                if not r_email or not r_senha:
                    st.error("Preencha todos os campos.")
                elif r_senha != r_conf:
                    st.error("As senhas não coincidem.")
                elif len(r_senha) < 6:
                    st.error("Senha deve ter pelo menos 6 caracteres.")
                else:
                    ok, msg = registrar(r_email, r_senha)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    st.stop()
