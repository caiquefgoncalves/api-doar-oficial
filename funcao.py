from flask_bcrypt import generate_password_hash, check_password_hash
import qrcode
import os
import unicodedata
from flask import jsonify

# Importar o con da main
from db import conexao

# Bibliotecas para envio de e-mail
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Bibliotecas para token
import jwt
import datetime

# Função para verificar existente
def verificar_existente(valor, tipo, id_usuarios = None):
    # Por padrão, o id_usuario é none (quando não passamos na hora de chamar a função)

    # Cria conexão com o banco
    con = conexao()
    cur = con.cursor()
    try:

        # Verifica CPF/CNPJ
        if tipo == 1:
            # Se estiver editando um usuário (ignora o próprio id)
            if id_usuarios:
                cur.execute("""SELECT 1
                               FROM USUARIOS
                               WHERE CPF_CNPJ = ? AND ID_USUARIOS != ?""", (valor, id_usuarios))
            else:
                # Verifica se já existe
                cur.execute("""SELECT 1
                           FROM USUARIOS
                           WHERE CPF_CNPJ = ?""", (valor,))

        # Verifica e-mail
        elif tipo == 2:
            # Se estiver editando (ignora o próprio id)
            if id_usuarios:
                cur.execute("""SELECT 1
                               FROM USUARIOS
                               WHERE EMAIL = ? AND ID_USUARIOS != ?""", (valor, id_usuarios))
            else:
                # Verifica se já existe
                cur.execute("""SELECT 1
                           FROM USUARIOS
                           WHERE EMAIL = ?""", (valor, ))

        # Se não encontrou, pode usar
        if not cur.fetchone():
            return True
        return False

    except Exception as e:
        return False
    finally:
        cur.close()
        con.close()


# Verifica se as senhas são iguais
def senha_correspondente(senha, confirmar_senha):
    try:
        if senha == confirmar_senha:
            return True
        return False
    except Exception as e:
        return False


# Verifica se a senha é forte
def senha_forte(senha):
    try:
        # Verifica tamanho mínimo
        if len(senha) < 8:
            return False

        # Critérios da senha
        criterios = {
            "maiuscula": False,
            "minuscula": False,
            "numero": False,
            "especial": False
        }

        # Percorre cada caractere
        for s in senha:
            if s.isupper():
                criterios["maiuscula"] = True
            elif s.islower():
                criterios["minuscula"] = True
            elif s.isdigit():
                criterios["numero"] = True
            elif s.isalnum() is False:
                criterios["especial"] = True

        # Verifica se todos os critérios foram atendidos
        if criterios["maiuscula"] == True and criterios["minuscula"] == True and criterios["numero"] == True and criterios["especial"] == True:
            return True

        return False

    except Exception as e:
        return False


# Verifica se a senha já foi usada antes
def senha_antiga(id_usuarios, nova_senha):
    # Cria conexão
    con = conexao()
    cursor = con.cursor()
    try:
        # Busca senha atual
        cursor.execute('SELECT senha FROM usuarios WHERE id_usuarios = ?', (id_usuarios, ))
        senha_atual_hash = cursor.fetchone()[0]

        # Busca últimas senhas usadas
        cursor.execute('SELECT FIRST 2 SENHA_HASH FROM HISTORICO_SENHA WHERE id_usuarios = ? ORDER BY DATA_ALTERACAO',
                   (id_usuarios,))
        ultimas_senhas = cursor.fetchall()

        # Busca a senha mais antiga do histórico
        cursor.execute(
            'SELECT FIRST 1 ID_HISTORICO_SENHA FROM HISTORICO_SENHA WHERE id_usuarios = ? ORDER BY DATA_ALTERACAO ASC',
            (id_usuarios,))
        tem_senha = cursor.fetchone()

        if tem_senha:
            senha_mais_antiga = tem_senha[0]

        # Verifica se a nova senha já foi usada
        for u in ultimas_senhas:
            senha_antiga = u[0]
            if check_password_hash(senha_antiga, nova_senha):
                return False

        # Verifica com a senha atual
        if check_password_hash(senha_atual_hash, nova_senha):
            return False

        # Data da alteração
        data_alteracao = datetime.datetime.utcnow()

        # Salva senha atual no histórico
        cursor.execute("INSERT INTO HISTORICO_SENHA(id_usuarios, SENHA_HASH, data_Alteracao) VALUES(?, ?, ?)",
                       (id_usuarios, senha_atual_hash, data_alteracao))

        # Remove códigos de recuperação antigos
        cursor.execute('DELETE FROM RECUPERACAO_SENHA WHERE id_usuarios = ?', (id_usuarios,))

        # Mantém apenas as últimas 2 senhas no histórico
        if ultimas_senhas:
            if len(ultimas_senhas) == 2:
                cursor.execute(""" DELETE FROM HISTORICO_SENHA
                                   WHERE ID_HISTORICO_SENHA = ?""",
                               (senha_mais_antiga,))

        con.commit()

        return True

    except Exception as e:
        print(e)
        return False


# Função para enviar e-mail
def enviando_email(destinatario, assunto, html):
    # Dados do remetente
    user = 'doar.plataformadoacoes@gmail.com'
    senha = 'jxwf uxid qaga hhah'

    # Monta mensagem
    msg = MIMEText(html, 'html')
    msg['From'] = user
    msg['To'] = destinatario
    msg['Subject'] = assunto

    try:
        # Conecta no servidor SMTP
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)

        # Faz login
        server.login(user, senha)

        # Envia e-mail
        server.sendmail(user, [destinatario], msg.as_string())
    finally:
        server.quit()


# Gera token de autenticação
def gerar_token(tipo, id_usuarios, tempo):
    # Dados do token
    payload = { 'tipo': tipo,
                'id_usuarios': id_usuarios,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=tempo)
               }

    # Chave secreta
    senha_secreta = current_app.config['SECRET_KEY']

    # Cria token
    token = jwt.encode(payload, senha_secreta, algorithm='HS256')

    return token


# Decodifica token
from flask import request
from flask import current_app
import jwt


def decodificar_token():
    try:
        token = request.cookies.get("acess_token")

        if not token:
            token = request.args.get('token')

        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split('Bearer ')[1]

        if not token:
            return False

        senha_secreta = current_app.config['SECRET_KEY']
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])

        return {'tipo': payload['tipo'], 'id_usuarios': payload['id_usuarios']}

    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False
    except Exception:
        return False


def validar_adm():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário. Faça login.'}), 401
    if token_data['tipo'] != 0:
        return jsonify({'error': 'Apenas administradores podem acessar esta rota'}), 403
    return None


def gerar_qr_pix(chave_pix, nome, cidade, id_ong, pasta_base, valor=None, projeto=False):
    def limpar(texto, max_len):
        if not texto:
            return ""
        texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
        return texto.strip().upper()[:max_len]

    # 🔹 AJUSTE: garantir cidade válida mesmo vindo zoada
    cidade = limpar((cidade or "BRASIL").split(",")[0], 15)
    nome = limpar(nome, 25)

    if not cidade:
        cidade = "BRASIL"

    # 🔹 FUNÇÃO PRA MONTAR CAMPOS (necessário pro Pix)
    def campo(id_campo, valor):
        return f"{id_campo}{len(valor):02}{valor}"

    # 🔹 CORREÇÃO PRINCIPAL: montar campo 26 corretamente
    gui = campo("00", "BR.GOV.BCB.PIX")
    chave = campo("01", chave_pix)
    merchant = campo("26", gui + chave)

    # 🔹 Montando payload
    payload = (
            campo("00", "01") +
            merchant +
            campo("52", "0000") +
            campo("53", "986")
    )

    if valor:
        valor_str = f"{float(valor):.2f}"
        payload += campo("54", valor_str)

    payload += (
            campo("58", "BR") +
            campo("59", nome) +
            campo("60", cidade) +
            campo("62", campo("05", "***")) +
            "6304"
    )

    def crc16(payload):
        polinomio = 0x1021
        resultado = 0xFFFF

        for byte in payload.encode():
            resultado ^= byte << 8
            for a in range(8):
                if resultado & 0x8000:
                    resultado = (resultado << 1) ^ polinomio
                else:
                    resultado <<= 1
                resultado &= 0xFFFF

        return format(resultado, '04X')

    payload_final = payload + crc16(payload)

    # CORRIGIDO: garantir que id_ong seja string para o nome do arquivo
    try:
        id_ong_str = str(int(id_ong))  # Converte para inteiro e depois para string
    except (ValueError, TypeError):
        id_ong_str = str(id_ong).replace('.', '_')  # Fallback se não for número

    if projeto == True:
        nome_arquivo = f'pix_doacao_{id_ong_str}.jpeg'
    else:
        nome_arquivo = f'pix_ong_{id_ong_str}.jpeg'

    pasta = os.path.join(pasta_base, 'Pix')
    os.makedirs(pasta, exist_ok=True)

    caminho = os.path.join(pasta, nome_arquivo)

    qr = qrcode.make(payload_final)
    qr.save(caminho)

    return nome_arquivo, payload_final


def formatar_cpf(cpf):
    if not cpf:
        return "-"
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def header(pdf, titulo):
    azul = (12, 89, 139)

    pdf.set_font("Arial", "B", 18)
    pdf.set_text_color(*azul)
    pdf.cell(0, 10, f"Relatório {titulo}", ln=True, align="C")

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, "Plataforma Doar+", ln=True, align="C")

    pdf.ln(5)

    pdf.set_draw_color(*azul)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)


def footer(pdf):
    azul = (12, 89, 139)
    azul_claro = (22, 124, 191)
    rosa = (246, 86, 130)
    laranja = (247, 181, 103)

    # Número da página
    pdf.set_y(-15)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, f"Página {pdf.page_no()}", align="C")

    # Linha decorativa
    pdf.set_y(-18)
    largura = 190 / 4
    cores = [azul, azul_claro, laranja, rosa]
    x = 10

    for cor in cores:
        pdf.set_fill_color(*cor)
        pdf.rect(x, pdf.get_y(), largura, 4, 'F')
        x += largura

def resumo_3_colunas(pdf, dados):
    azul = (12, 89, 139)
    largura = 190 / 3
    y_inicial = pdf.get_y()

    for titulo, valor in dados:
        x_atual = pdf.get_x()

        # título
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(largura, 5, titulo.upper(), align="C")

        pdf.set_xy(x_atual, y_inicial + 5)

        # valor
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(*azul)
        pdf.multi_cell(largura, 7, str(valor), align="C")

        pdf.set_xy(x_atual + largura, y_inicial)

    pdf.ln(25)

def ranking_lista(pdf, titulo, dados, tipo="moeda"):
    azul = (12, 89, 139)
    cinza = (120, 120, 120)

    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, titulo, ln=True)

    pdf.ln(3)

    for i, (nome, valor) in enumerate(dados, start=1):

        # badge posição
        pdf.set_fill_color(*azul)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(10, 6, f"{i}º", align="C", fill=True)

        # nome
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(90, 6, f" {nome}")

        # valor
        pdf.set_text_color(*cinza)
        pdf.set_font("Arial", "B", 11)

        if tipo == "moeda":
            texto_valor = f"R$ {valor:.2f}".replace(",", ".").replace(".", ",")
        elif tipo == "voluntariado":
            texto_valor = str(valor) + " voluntário(s)"
        else:
            texto_valor = str(valor) + " curtida(s)"

        pdf.cell(0, 6, texto_valor, ln=True, align="R")

        pdf.ln(2)

    pdf.ln(5)

def formatar_cnpj(cnpj):

    if not cnpj:
        return ""

    cnpj = ''.join(filter(str.isdigit, str(cnpj)))
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"
    return cnpj