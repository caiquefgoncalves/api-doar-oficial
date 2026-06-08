from flask import jsonify, request, make_response, render_template
from funcao import senha_forte, enviando_email, gerar_token, verificar_existente, senha_correspondente, senha_antiga, decodificar_token, validar_adm
from flask_bcrypt import generate_password_hash, check_password_hash
from main import app
from db import conexao
import threading
import os
import datetime
from random import randint
import random


# Criar usuário
@app.route('/criar_usuarios', methods=['POST'])
def criar_usuarios():
    nome = request.form.get('nome', None)
    email = request.form.get('email', None)
    cpf_cnpj = request.form.get('cpf_cnpj', None)
    telefone = request.form.get('telefone', None)
    descricao_breve = request.form.get('descricao_breve', None)
    descricao_longa = request.form.get('descricao_longa', None)
    cod_banco = request.form.get('cod_banco', None)
    num_agencia = request.form.get('num_agencia', None)
    num_conta = request.form.get('num_conta', None)
    tipo_conta = request.form.get('tipo_conta', None)
    chave_pix = request.form.get('chave_pix', None)
    categoria = request.form.get('categoria', None)
    localizacao = request.form.get('localizacao', None)
    senha = request.form.get('senha')
    confirmar_senha = request.form.get('confirmar_senha')
    tipo = request.form.get('tipo', 1)

    try:
        tipo = int(tipo)
    except (ValueError, TypeError):
        tipo = 1

    foto_perfil = request.files.get('foto_perfil')
    data_cadastro = datetime.datetime.now()
    ativo = 1

    if tipo == 2:
        aprovacao = 0
    else:
        aprovacao = None

    email_confirmacao = 0

    # Mensagem padrão de agradecimento para ONGs
    mensagem_padrao = "Agradecemos imensamente por sua contribuição! Sua doação faz a diferença e nos ajuda a transformar vidas."

    # Só ADM pode criar outro ADM
    if tipo == 0:
        token_data = decodificar_token()
        print(f"DEBUG - Token data: {token_data}")
        if token_data == False:
            return jsonify({'error': 'Token necessário para criar ADM'}), 401
        if token_data['tipo'] != 0:
            return jsonify({'error': 'Apenas administradores podem criar contas de ADM'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        if nome == None or nome.strip() == '':
            return jsonify({"error": "Nome é obrigatório"}), 400
        if cpf_cnpj == None or cpf_cnpj.strip() == '':
            return jsonify({"error": "CPF/CNPJ é obrigatório"}), 400
        if email == None or email.strip() == '':
            return jsonify({"error": "E-mail é obrigatório"}), 400
        if verificar_existente(cpf_cnpj, 1) == False:
            return jsonify({"error": "CPF ou CNPJ já cadastrado"}), 400
        if verificar_existente(email, 2) == False:
            return jsonify({"error": "E-mail já cadastrado"}), 400
        if senha_forte(senha) == False:
            return jsonify({"error": "Senha fraca"}), 400
        if senha_correspondente(senha, confirmar_senha) == False:
            return jsonify({"error": "Senhas não correspondem"}), 400

        senha_cripto = generate_password_hash(senha).decode('utf-8')
        codigo_confirmacao = str(randint(100000, 999999))
        tentativa = 0

        # Inserir com a mensagem de agradecimento padrão para ONGs
        cur.execute("""INSERT INTO USUARIOS (NOME, EMAIL, SENHA, CPF_CNPJ, TELEFONE,
                                             DESCRICAO_BREVE, DESCRICAO_LONGA, APROVACAO,
                                             COD_BANCO, NUM_AGENCIA, NUM_CONTA, TIPO_CONTA,
                                             CHAVE_PIX, CATEGORIA, ATIVO, LOCALIZACAO,
                                             TIPO, DATA_CADASTRO, EMAIL_CONFIRMACAO,
                                             CODIGO_CONFIRMACAO, TENTATIVA, MENSAGEM_AGRADECIMENTO)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING ID_USUARIOS""",
                    (nome, email, senha_cripto, cpf_cnpj, telefone, descricao_breve,
                     descricao_longa, aprovacao, cod_banco, num_agencia, num_conta, tipo_conta,
                     chave_pix, categoria, ativo, localizacao, tipo, data_cadastro, email_confirmacao,
                     codigo_confirmacao, tentativa, mensagem_padrao if tipo == 2 else None))

        codigo_usuarios = cur.fetchone()[0]
        con.commit()

        if foto_perfil:
            try:
                nome_imagem = f'{codigo_usuarios}.jpeg'
                caminho_imagem_destino = os.path.join(app.config['UPLOAD_FOLDER'], 'Usuarios')
                os.makedirs(caminho_imagem_destino, exist_ok=True)
                caminho_imagem = os.path.join(caminho_imagem_destino, nome_imagem)
                foto_perfil.save(caminho_imagem)
            except Exception as e:
                print(f"ERRO ao salvar imagem: {e}")

        assunto = 'Código de Confirmação de E-mail'
        mensagem = 'Bem-vindo(a) à Doar +! Confirme seu e-mail.'
        codigo = codigo_confirmacao
        html = render_template('template_email.html', mensagem=mensagem, codigo=codigo)
        threading.Thread(target=enviando_email, args=(email, assunto, html)).start()

        return jsonify(
            {'message': "Usuário cadastrado com sucesso", 'usuario': {'tipo': tipo, 'nome': nome, 'email': email}}), 201

    except Exception as e:
        print(f"ERRO ao cadastrar usuário: {e}")
        return jsonify({'message': f'Erro: {e}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/editar_usuarios/<int:id_usuarios>', methods=['PUT'])
def editar_usuarios(id_usuarios):

    con = conexao()

    cur = con.cursor()


    token = request.form.get('token', None)

    try:

        if token == None or token.strip() == '':
            return jsonify({'error': 'Token necessário para autenticação'}), 401


        token_data = decodificar_token(token) if token else None


        if not token_data or token_data == False:

            token_data = decodificar_token()


        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL, SENHA, CPF_CNPJ, TELEFONE,
                              DESCRICAO_BREVE, DESCRICAO_LONGA, APROVACAO, COD_BANCO,
                              NUM_AGENCIA, NUM_CONTA, TIPO_CONTA, CHAVE_PIX, CATEGORIA,
                              ATIVO, LOCALIZACAO, TIPO, DATA_CADASTRO, EMAIL_CONFIRMACAO,
                              CODIGO_CONFIRMACAO, TENTATIVA
                       FROM USUARIOS WHERE ID_USUARIOS = ?""", (id_usuarios,))

        tem_usuario = cur.fetchone()

        if tem_usuario == None:
            return jsonify({"error": "Usuário não encontrado"}), 404


        nome = request.form.get('nome', tem_usuario[1])
        email = request.form.get('email', tem_usuario[2])
        cpf_cnpj = request.form.get('cpf_cnpj', tem_usuario[4])
        telefone = request.form.get('telefone', tem_usuario[5])
        descricao_breve = request.form.get('descricao_breve', tem_usuario[6])
        descricao_longa = request.form.get('descricao_longa', tem_usuario[7])
        aprovacao = tem_usuario[8]
        cod_banco = request.form.get('cod_banco', tem_usuario[9])
        num_agencia = request.form.get('num_agencia', tem_usuario[10])
        num_conta = request.form.get('num_conta', tem_usuario[11])
        tipo_conta = request.form.get('tipo_conta', tem_usuario[12])
        chave_pix = request.form.get('chave_pix', tem_usuario[13])
        categoria = request.form.get('categoria', tem_usuario[14])
        ativo = tem_usuario[15]
        localizacao = request.form.get('localizacao', tem_usuario[16])
        senha = request.form.get('senha', None)
        confirmar_senha = request.form.get('confirmar_senha', None)
        foto_perfil = request.files.get('foto_perfil')
        tipo = tem_usuario[17]
        data_cadastro = tem_usuario[18]
        email_confirmacao = tem_usuario[19]
        codigo_confirmacao = tem_usuario[20]
        tentativa = tem_usuario[21]


        if not nome or nome.strip() == '':
            return jsonify({"error": "Nome é uma informação obrigatória."}), 400

        if not cpf_cnpj or cpf_cnpj.strip() == '':
            return jsonify({"error": "CPF/CNPJ é uma informação obrigatória."}), 400

        if not email or email.strip() == '':
            return jsonify({"error": "E-mail é uma informação obrigatória."}), 400


        if cpf_cnpj != tem_usuario[4]:
            if verificar_existente(cpf_cnpj, 1, id_usuarios) == False:
                return jsonify({"error": "CPF ou CNPJ já cadastrado por outro usuário."}), 400

        if email != tem_usuario[2]:
            if verificar_existente(email, 2, id_usuarios) == False:
                return jsonify({"error": "E-mail já cadastrado por outro usuário."}), 400

        # Processamento de nova senha se preenchida
        if senha and senha.strip() != '':
            if senha_forte(senha) == False:
                return jsonify({
                                   "error": "Senha fraca. A senha deve conter pelo menos 8 caracteres, incluindo letras maiúsculas, minúsculas, números e caracteres especiais."}), 400

            if senha_correspondente(senha, confirmar_senha) == False:
                return jsonify({"error": "Senhas não correspondem."}), 400

            if senha_antiga(id_usuarios, senha) == False:
                return jsonify({"error": "A senha nova não pode ser igual às últimas 3 utilizadas."}), 400

            nova_senha_hash = generate_password_hash(senha).decode('utf-8')
        else:
            nova_senha_hash = tem_usuario[3]


        if email != tem_usuario[2]:
            codigo_confirmacao = randint(100000, 999999)
            email_confirmacao = 0

            assunto = 'Código de Confirmação de E-mail'
            mensagem = 'Percebemos que você alterou seu e-mail, por isso é necessário confirmar novamente.'
            html = render_template('template_email.html', mensagem=mensagem, codigo=codigo_confirmacao)

            threading.Thread(target=enviando_email, args=(email, assunto, html)).start()

        # Executa o UPDATE no Banco de Dados
        cur.execute("""UPDATE USUARIOS
                       SET NOME               = ?,
                           EMAIL              = ?,
                           SENHA              = ?,
                           CPF_CNPJ           = ?,
                           TELEFONE           = ?,
                           DESCRICAO_BREVE    = ?,
                           DESCRICAO_LONGA    = ?,
                           APROVACAO          = ?,
                           COD_BANCO          = ?,
                           NUM_AGENCIA        = ?,
                           NUM_CONTA          = ?,
                           TIPO_CONTA         = ?,
                           CHAVE_PIX          = ?,
                           CATEGORIA          = ?,
                           ATIVO              = ?,
                           LOCALIZACAO        = ?,
                           TIPO               = ?,
                           DATA_CADASTRO      = ?,
                           EMAIL_CONFIRMACAO  = ?,
                           CODIGO_CONFIRMACAO = ?,
                           TENTATIVA          = ?
                       WHERE ID_USUARIOS = ?""",
                    (nome, email, nova_senha_hash, cpf_cnpj, telefone, descricao_breve,
                     descricao_longa, aprovacao, cod_banco, num_agencia, num_conta, tipo_conta,
                     chave_pix, categoria, ativo, localizacao, tipo, data_cadastro,
                     email_confirmacao, codigo_confirmacao, tentativa, id_usuarios))

        con.commit()

        # Salva a imagem de perfil localmente se houver upload
        if foto_perfil:
            nome_imagem = f'{id_usuarios}.jpeg'
            caminho_imagem_destino = os.path.join(app.config['UPLOAD_FOLDER'], "Usuarios")
            os.makedirs(caminho_imagem_destino, exist_ok=True)
            foto_perfil.save(os.path.join(caminho_imagem_destino, nome_imagem))

        return jsonify({
            'message': "Usuário editado com sucesso",
            'usuario': {
                'tipo': tipo, 'nome': nome, 'email': email, 'cpf_cnpj': cpf_cnpj, 'telefone': telefone,
                'descricao_breve': descricao_breve, 'descricao_longa': descricao_longa,
                'cod_banco': cod_banco, 'num_agencia': num_agencia, 'num_conta': num_conta,
                'tipo_conta': tipo_conta, 'chave_pix': chave_pix, 'categoria': categoria, 'localizacao': localizacao
            }
        }), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO EDITAR USUARIO: {str(e)}")
        return jsonify({'message': f'Erro ao consultar o banco de dados: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# Excluir usuário
@app.route('/deletar_usuarios/<int:id_usuarios>', methods=['DELETE'])
def deletar_usuarios(id_usuarios):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    # Apenas ADM ou o próprio usuário pode excluir
    if token_data['tipo'] != 0 and token_data['id_usuarios'] != id_usuarios:
        return jsonify({'error': 'Você não tem permissão para excluir este usuário'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("SELECT ID_USUARIOS FROM USUARIOS WHERE ID_USUARIOS = ?", (id_usuarios,))
        if not cur.fetchone():
            return jsonify({"error": "Usuário não encontrado"}), 404

        cur.execute("DELETE FROM HISTORICO_SENHA WHERE ID_USUARIOS = ?", (id_usuarios,))
        cur.execute("DELETE FROM RECUPERACAO_SENHA WHERE ID_USUARIOS = ?", (id_usuarios,))
        cur.execute("DELETE FROM USUARIOS WHERE ID_USUARIOS = ?", (id_usuarios,))
        con.commit()

        return jsonify({"message": "Usuário excluído com sucesso"}), 200

    except Exception as e:
        return jsonify({'message': f'Erro: {e}'}), 500
    finally:
        cur.close()
        con.close()


# Ativar usuário
@app.route('/ativar_usuarios/<int:id_usuarios>', methods=['PUT'])
def ativar_usuarios(id_usuarios):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 0:
        return jsonify({'error': 'Apenas administradores podem ativar usuários'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("UPDATE USUARIOS SET ATIVO = 1 WHERE ID_USUARIOS = ?", (id_usuarios,))
        con.commit()
        return jsonify({'message': 'Usuário ativado com sucesso!'}), 200
    finally:
        cur.close()
        con.close()


# Inativar usuário
@app.route('/inativar_usuarios/<int:id_usuarios>', methods=['PUT'])
def inativar_usuarios(id_usuarios):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 0 and token_data['id_usuarios'] != id_usuarios:
        return jsonify({'error': 'Você não tem permissão para inativar este usuário'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("SELECT ID_USUARIOS FROM USUARIOS WHERE ID_USUARIOS = ?", (id_usuarios,))
        if not cur.fetchone():
            return jsonify({"error": "Usuário não encontrado"}), 404

        cur.execute("UPDATE USUARIOS SET ATIVO = 0 WHERE ID_USUARIOS = ?", (id_usuarios,))
        con.commit()
        return jsonify({"message": "Usuário inativado com sucesso"}), 200
    except Exception as e:
        return jsonify({'message': f'Erro: {e}'}), 500
    finally:
        cur.close()
        con.close()


# Listar usuários
@app.route('/listar_usuarios', methods=['GET'])
def listar_usuarios():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 0:
        return jsonify({'error': 'Apenas administradores podem listar usuários'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL, SENHA, CPF_CNPJ, TELEFONE,
                              DESCRICAO_BREVE, DESCRICAO_LONGA, APROVACAO, COD_BANCO,
                              NUM_AGENCIA, NUM_CONTA, TIPO_CONTA, CHAVE_PIX, CATEGORIA,
                              ATIVO, LOCALIZACAO, TIPO, DATA_CADASTRO, EMAIL_CONFIRMACAO,
                              CODIGO_CONFIRMACAO, TENTATIVA
                       FROM USUARIOS""")
        usuarios = cur.fetchall()
        if usuarios:
            return jsonify({'usuarios': usuarios}), 200
        else:
            return jsonify({'error': 'Nenhum usuário encontrado'}), 404
    except Exception as e:
        return jsonify({'message': f'Erro: {e}'}), 500
    finally:
        cur.close()
        con.close()


# Buscar usuários por CPF/CNPJ
@app.route('/buscar_usuarios', methods=['GET'])
def buscar_usuarios():
    # Pega valor de busca
    cpf_cnpj = request.json.get('cpf_cnpj')

    # Cria conexão
    con = conexao()

    # Abre cursor
    cur = con.cursor()

    try:
        # Verifica token
        if decodificar_token() == False:
            return jsonify({'error': 'Token necessário'}), 401

        # Apenas administrador pode buscar
        if decodificar_token()['tipo'] != 0:
            return jsonify({'error': 'É necessário ser administrador para isso'}), 401

        # Adiciona o % antes e depois pra poder buscar mesmo se não for o valor completo
        valor_busca = f"%{cpf_cnpj}%"

        # Executa consulta
        cur.execute("""SELECT ID_USUARIOS,
                              NOME,
                              EMAIL,
                              SENHA,
                              CPF_CNPJ,
                              TELEFONE,
                              DESCRICAO_BREVE,
                              DESCRICAO_LONGA,
                              APROVACAO,
                              COD_BANCO,
                              NUM_AGENCIA,
                              NUM_CONTA,
                              TIPO_CONTA,
                              CHAVE_PIX,
                              CATEGORIA,
                              ATIVO,
                              LOCALIZACAO,
                              TIPO,
                              DATA_CADASTRO,
                              EMAIL_CONFIRMACAO,
                              CODIGO_CONFIRMACAO,
                              TENTATIVA
                       FROM USUARIOS
                       WHERE cpf_cnpj LIKE ?""", (valor_busca,))

        # Armazena resultado
        usuarios = cur.fetchall()

        # Retorna resultado
        if usuarios:
            return jsonify({'usuarios': usuarios}), 200
        else:
            return jsonify({
                'error': 'Não foi possível encontrar usuários com esse cpf/cnpj'
            }), 404

    except Exception as e:
        return jsonify({'message': f'Erro ao consultar o banco de dados: {e}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/login', methods=['POST'])
def login():
    cpf_cnpj = request.json.get('cpf_cnpj')
    senha = request.json.get('senha')

    # Verifica se já está logado
    if decodificar_token() != False:
        return jsonify({'error': 'Você já está logado. Faça logout primeiro.'}), 400

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""SELECT ID_USUARIOS, TIPO, NOME, CPF_CNPJ, SENHA, TENTATIVA,
        EMAIL_CONFIRMACAO, ATIVO, APROVACAO
        FROM USUARIOS WHERE CPF_CNPJ = ?""", (cpf_cnpj,))

        usuario = cur.fetchone()
        if not usuario:
            return jsonify({"error": "Usuário não encontrado"}), 404

        id_usuarios = usuario[0]
        tipo = usuario[1]
        nome = usuario[2]
        senha_hash = usuario[4]
        tentativa = usuario[5]
        email_confirmacao = usuario[6]
        ativo = usuario[7]
        aprovacao = usuario[8]

        cur.execute("""SELECT ID_VOLUNTARIADO FROM VOLUNTARIADO
        WHERE ID_USUARIOS = ?""", (id_usuarios,))

        voluntario = cur.fetchone()

        if voluntario:
            voluntariado = True
        else:
            voluntariado = False

        foto_perfil = f'{id_usuarios}.jpeg'

        if tentativa > 3 and tipo != 0:
            return jsonify({"error": "Usuário bloqueado! Contate o administrador"}), 400
        if ativo == 0:
            return jsonify({"error": "Usuário inativado"}), 400
        if email_confirmacao == 0:
            return jsonify({"error": "Verifique o e-mail antes de logar!"}), 400
        if tipo == 2:
            if aprovacao == 0:
                return jsonify({"error": "Sua ONG ainda está pendente de aprovação"}), 400
            elif aprovacao == 2:
                return jsonify({"error": "Sua ONG foi reprovada. Contate o administrador"}), 400

        if check_password_hash(senha_hash, senha):
            if tentativa > 0:
                cur.execute("UPDATE USUARIOS SET TENTATIVA = 0 WHERE ID_USUARIOS = ?", (id_usuarios,))
                con.commit()

            token = gerar_token(tipo, id_usuarios, 1440)
            resp = make_response(jsonify({
            'message': f'Bem-vindo {nome}!',
            'nome': nome,
            'token': token,
            'voluntariado': voluntariado,
            'foto_perfil': foto_perfil
            }))
            resp.set_cookie('acess_token', token, httponly=True, secure=False, samesite='Lax', path="/", max_age=7600)
            return resp

        if tipo != 0:
            tentativa = tentativa + 1
        cur.execute("UPDATE USUARIOS SET TENTATIVA = ? WHERE ID_USUARIOS = ?", (tentativa, id_usuarios))
        con.commit()

        return jsonify({"error": "Senha incorreta"}), 400

    except Exception as e:
        print(e)
        return jsonify({'message': f'Erro: {e}'}), 500
    finally:
        cur.close()
        con.close()

# Logout
@app.route('/logout', methods=['POST'])
def logout():
    if decodificar_token() == False:
        return jsonify({'message': 'Você já está deslogado!'})

    resp = make_response(jsonify({'message': 'Deslogado com sucesso!'}))
    resp.set_cookie('acess_token', '', httponly=True, secure=False, samesite='None', path="/", max_age=0)
    return resp


# Desbloquear usuário
@app.route('/desbloquear_usuarios/<int:id_usuarios>', methods=['PUT'])
def desbloquear_usuarios(id_usuarios):
    # Cria conexão
    con = conexao()

    # Abre cursor
    cur = con.cursor()

    try:
        # Verifica token
        if decodificar_token() == False:
            return jsonify({'error': 'Token necessário'}), 401

        # Apenas administrador pode desbloquear
        if decodificar_token()['tipo'] == 0:
            tentativa = 0

            # Zera tentativas
            cur.execute("""UPDATE USUARIOS
                           SET TENTATIVA = ?
                           WHERE ID_USUARIOS = ?""", (tentativa, id_usuarios))

            con.commit()

            return jsonify({'message': 'Usuário desbloqueado com sucesso!'})

        return jsonify({'error': 'É necessário ser administrador'})
    finally:
        cur.close()
        con.close()


# Confirmar e-mail
@app.route('/confirmar_email', methods=['POST'])
def confirmar_email():
    # Pega código digitado
    codigo_digitado = (request.json.get('codigo_digitado'))

    # Cria conexão
    con = conexao()

    # Abre cursor
    cursor = con.cursor()

    # Verifica se código foi enviado
    if not codigo_digitado:
        return jsonify({'error': 'Preencha o código de confirmação'}), 400

    try:
        # Busca usuário pelo código
        cursor.execute('SELECT id_usuarios FROM usuarios WHERE codigo_confirmacao = ?', (str(codigo_digitado, ),))
        usuario = cursor.fetchone()

        # Verifica se código é válido
        if not usuario:
            return jsonify({'error': 'Código incorreto'}), 404

        id_usuarios = usuario[0]

        # Atualiza confirmação de e-mail
        cursor.execute('UPDATE usuarios SET email_confirmacao = 1, codigo_confirmacao = NULL WHERE id_usuarios = ?',
                       (id_usuarios, ))

        con.commit()

        return jsonify({'message': 'Email confirmado com sucesso!'}), 200

    except Exception as e:
        return jsonify({'error': f'Erro: {e}'})
    finally:
        cursor.close()
        con.close()


# Esqueci senha
@app.route('/esqueci_senha', methods=['POST'])
def esqueci_senha():
    # Pega e-mail
    email = request.json.get('email')

    # Verifica se foi enviado
    if not email:
        return jsonify({'error': "Por favor, envie o e-mail."}), 400

    # Cria conexão
    con = conexao()

    # Abre cursor
    cursor = con.cursor()

    try:
        # Busca usuário e verifica se está ativo
        cursor.execute("SELECT id_usuarios, NOME, ATIVO FROM usuarios WHERE EMAIL = ?", (email,))
        usuario = cursor.fetchone()

        # Verifica se usuário existe
        if not usuario:
            return jsonify({'error': "Usuário não encontrado"}), 404

        id_usuarios = usuario[0]
        nome = usuario[1]
        ativo = usuario[2]

        # Verifica se está ativo
        if ativo == 0:
            return jsonify({"error": "Esse usuário está inativado"}), 403

        # Busca código de recuperação existente
        cursor.execute("""SELECT CODIGO, DATA_EXPIRACAO
                          FROM RECUPERACAO_SENHA
                          WHERE ID_usuarios = ?""", (id_usuarios,))

        # Armazena resultado
        dados_recuperacao = cursor.fetchone()

        # Se já existir código válido, reutiliza
        if dados_recuperacao and dados_recuperacao[1] > datetime.datetime.now():
            codigo = dados_recuperacao[0]

            assunto = 'Código de Recuperação de Senha'
            mensagem = 'Recebemos uma solicitação para recuperar sua senha'

            html = render_template('template_email.html', mensagem=mensagem, codigo=codigo)

            # Reenvia código
            threading.Thread(target=enviando_email,
                             args=(email, assunto, html)
                             ).start()

            return jsonify({
                'message': "Percebemos que seu código ainda está ativo, por isso ele foi reenviado para o e-mail!"}), 200

        # Remove códigos antigos
        cursor.execute("DELETE FROM RECUPERACAO_SENHA WHERE id_usuarios = ?", (id_usuarios,))

        # Gera novo código
        codigo = randint(100000, 999999)

        # Define validade (30 minutos)
        validade = datetime.datetime.now() + datetime.timedelta(minutes=30)

        # Insere novo código
        cursor.execute("""
                       INSERT INTO RECUPERACAO_SENHA (id_usuarios, CODIGO, DATA_EXPIRACAO)
                       VALUES (?, ?, ?)
                       """, (id_usuarios, codigo, validade))

        con.commit()

        # Prepara envio de e-mail
        assunto = 'Código de Recuperação de Senha'
        mensagem = 'Recebemos uma solicitação para recuperar sua senha'

        html = render_template('template_email.html', mensagem=mensagem, codigo=codigo)

        # Envia e-mail
        threading.Thread(target=enviando_email,
                         args=(email, assunto, html)
                         ).start()

        return jsonify({'message': "Código enviado para o e-mail!"}), 200

    except Exception as e:
        con.rollback()
        return jsonify({'error': f"Erro interno: {e}"}), 500
    finally:
        cursor.close()
        con.close()


# Verificar código de recuperação
@app.route('/verificar_codigo', methods=['POST'])
def verificar_codigo():
    # Pega código digitado
    codigo_digitado = request.json.get('codigo_digitado')

    # Verifica se foi enviado
    if not codigo_digitado:
        return jsonify({'error': 'Preencha o código'}), 400

    # Cria conexão
    con = conexao()

    # Abre cursor
    cursor = con.cursor()

    try:
        # Busca código no banco
        cursor.execute('SELECT id_usuarios, data_expiracao FROM RECUPERACAO_SENHA WHERE codigo = ?', (codigo_digitado,))
        recuperacao = cursor.fetchone()

        # Verifica se código existe
        if not recuperacao:
            return jsonify({'error': 'Código incorreto!'}), 404

        id_usuarios = recuperacao[0]
        data_expiracao = recuperacao[1]

        # Verifica se código expirou
        if datetime.datetime.now() > data_expiracao:
            cursor.execute("DELETE FROM RECUPERACAO_SENHA WHERE id_usuarios = ?", (id_usuarios,))
            con.commit()
            return jsonify({'message': "Este código expirou. Solicite um novo."}), 400

        # Busca tipo do usuário
        cursor.execute("SELECT TIPO FROM USUARIOS WHERE ID_USUARIOS = ?", (id_usuarios,))
        tipo = cursor.fetchone()[0]

        # Gera token temporário
        token = gerar_token(tipo, id_usuarios, 1440)

        # Cria resposta com cookie
        resp = make_response(jsonify({'message': "Código correto! Você tem 5 minutos para alterar sua senha", 'token': token, 'id': id_usuarios}), 200)

        # Define cookie com token
        resp.set_cookie('acess_token', token,
                        httponly=True,
                        secure=False,
                        samesite='None',
                        path="/",
                        max_age=3600)

        return resp

    except Exception as e:
        return jsonify({'error': f'Erro: {e}'}), 500
    finally:
        cursor.close()
        con.close()


@app.route('/meus_dados', methods=['GET'])
def meus_dados():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    id_usuarios = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL, CPF_CNPJ, TELEFONE
        FROM USUARIOS WHERE ID_USUARIOS = ?""", (id_usuarios,))
        usuario = cur.fetchone()

        if not usuario:
            return jsonify({'error': 'Usuário não encontrado'}), 404

        cur.execute("""SELECT ID_VOLUNTARIADO FROM VOLUNTARIADO
        WHERE ID_USUARIOS = ?""", (id_usuarios,))
        voluntario = cur.fetchone()
        if voluntario:
            voluntario = True
        else:
            voluntario = False

        return jsonify({
            'usuario': {
            'id': usuario[0],
            'nome': usuario[1],
            'email': usuario[2],
            'cpf_cnpj': usuario[3],
            'telefone': usuario[4],
            'voluntario': voluntario
        }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# usuario.py - Rota de bloqueio/desbloqueio

@app.route('/admin/bloquear/<int:id_usuarios>', methods=['PUT'])
def bloquear(id_usuarios):
    """Bloqueia ou desbloqueia um usuário (ONG ou Doador)"""
    erro = validar_adm()
    if erro:
        return erro

    acao = request.json.get('acao', 'bloquear')
    motivo = request.json.get('motivo', '')

    con = conexao()
    cur = con.cursor()
    try:
        # Busca dados do usuário
        cur.execute("SELECT ID_USUARIOS, NOME, EMAIL, TIPO FROM USUARIOS WHERE ID_USUARIOS = ?", (id_usuarios,))
        usuario = cur.fetchone()

        if not usuario:
            return jsonify({'error': 'Usuário não encontrado'}), 404

        # Define o novo status (0 = bloqueado, 1 = ativo)
        novo_status = 0 if acao == 'bloquear' else 1

        # Atualiza o status do usuário
        cur.execute("UPDATE USUARIOS SET ATIVO = ? WHERE ID_USUARIOS = ?", (novo_status, id_usuarios))
        con.commit()

        # Se for bloqueio e tiver motivo, envia e-mail
        if acao == 'bloquear' and motivo:
            tipo_usuario = "ONG" if usuario[3] == 2 else "Doador"
            html = render_template('template_bloqueio_doador.html',
                                   nome=usuario[1],
                                   motivo=motivo,
                                   tipo=tipo_usuario)
            threading.Thread(target=enviando_email,
                             args=(usuario[2], f'Você foi bloqueado - Doar +', html)).start()

        mensagem = f'Usuário {usuario[1]} {"bloqueado" if acao == "bloquear" else "desbloqueado"} com sucesso!'
        return jsonify({'message': mensagem}), 200

    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()



@app.route('/buscar_mensagem_agradecimento', methods=['GET'])
def buscar_mensagem_agradecimento():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem acessar'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        id_ong = token_data['id_usuarios']
        cur.execute("SELECT MENSAGEM_AGRADECIMENTO FROM USUARIOS WHERE ID_USUARIOS = ?", (id_ong,))
        resultado = cur.fetchone()

        mensagem = resultado[0] if resultado and resultado[0] else ""

        return jsonify({'mensagem': mensagem}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()



@app.route('/salvar_mensagem_agradecimento', methods=['POST'])
def salvar_mensagem_agradecimento():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem acessar'}), 403

    data = request.get_json()
    mensagem = data.get('mensagem', '')

    if not mensagem.strip():
        return jsonify({'error': 'A mensagem não pode estar vazia'}), 400

    con = conexao()
    cur = con.cursor()

    try:
        id_ong = token_data['id_usuarios']
        cur.execute("UPDATE USUARIOS SET MENSAGEM_AGRADECIMENTO = ? WHERE ID_USUARIOS = ?", (mensagem, id_ong))
        con.commit()

        return jsonify({'message': 'Mensagem salva com sucesso!'}), 200
    except Exception as e:
        con.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()



@app.route('/ong_mensagem_agradecimento/<int:id_ong>', methods=['GET'])
def ong_mensagem_agradecimento(id_ong):
    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("SELECT MENSAGEM_AGRADECIMENTO, NOME FROM USUARIOS WHERE ID_USUARIOS = ?", (id_ong,))
        resultado = cur.fetchone()

        mensagem = resultado[0] if resultado and resultado[0] else ""
        nome_ong = resultado[1] if resultado else ""

        return jsonify({'mensagem': mensagem, 'ong_nome': nome_ong}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()

@app.route('/buscar_info', methods=['GET'])
def buscar_info():
    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("SELECT ID_EMPRESAS, NOME, SPAN_NOME, DESCRICAO, TEXTO_BANNER_PRINCIPAL, TEXTO_BANNER_SECUNDARIO, COR_PRIMARIA, COR_SECUNDARIA, COR_TERCIARIA, FONTE_TEXTO, FONTE_TITULO, FONTE_COR, FONTE_LOGO FROM EMPRESAS")
        empresa = cur.fetchone()

        if not empresa:
            return jsonify({'error': 'Empresa não encontrada'}), 404

        id_empresa = empresa[0]

        empresa_dic = {
            'nome': empresa[1],
            'span_nome': empresa[2],
            'descricao': empresa[3],
            'texto_banner_principal': empresa[4],
            'texto_banner_secundario': empresa[5],
            'cor_primaria': empresa[6],
            'cor_secundaria': empresa[7],
            'cor_terceria': empresa[8],
            'fonte_texto': empresa[9],
            'fonte_titulo': empresa[10],
            'fonte_cor': empresa[11],
            'fonte_logo': empresa[13] if len(empresa) > 13 else 'Playwrite US Trad',
            'logo': f'logo_{id_empresa}.jpeg',
            'banner': f'banner_{id_empresa}.jpeg'
        }

        return jsonify({'message': 'Informações recuperadas com sucesso', 'empresa': empresa_dic}), 200

    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/alterar_info', methods=['POST'])
def alterar_info():
    con = conexao()
    cur = con.cursor()
    try:
        # Busca os dados atuais
        cur.execute("""SELECT ID_EMPRESAS,
                              NOME,
                              SPAN_NOME,
                              DESCRICAO,
                              TEXTO_BANNER_PRINCIPAL,
                              TEXTO_BANNER_SECUNDARIO,
                              FONTE_COR,
                              COR_PRIMARIA,
                              COR_SECUNDARIA,
                              COR_TERCIARIA,
                              FONTE_TEXTO,
                              FONTE_TITULO,
                              FONTE_LOGO
                       FROM EMPRESAS""")

        empresa = cur.fetchone()

        if empresa == None:
            return jsonify({"error": "Empresa não encontrada"}), 404
        id_empresa = empresa[0]

        # Pega os dados enviados ou mantém os atuais
        nome = request.form.get('nome', empresa[1])
        span_nome = request.form.get('span_nome', empresa[2])
        descricao = request.form.get('descricao', empresa[3])
        texto_banner_principal = request.form.get('texto_banner_principal', empresa[4])
        texto_banner_secundario = request.form.get('texto_banner_secundario', empresa[5])
        fonte_cor = request.form.get('fonte_cor', empresa[6])
        cor_primaria = request.form.get('cor_primaria', empresa[7])
        cor_secundaria = request.form.get('cor_secundaria', empresa[8])
        cor_terciaria = request.form.get('cor_terciaria', empresa[9])
        fonte_texto = request.form.get('fonte_texto', empresa[10])
        fonte_titulo = request.form.get('fonte_titulo', empresa[11])
        fonte_logo = request.form.get('fonte_logo', empresa[13] if len(empresa) > 13 else 'Playwrite US Trad')
        logo = request.files.get('logo')
        banner = request.files.get('banner')

        # Verifica se o nome está vazio
        nome_sem_espacos = nome.strip()
        if nome_sem_espacos == '':
            return jsonify({"error": "Nome é uma informação obrigatória."}), 400

        # Atualiza os dados
        cur.execute("""UPDATE EMPRESAS
                       SET NOME = ?,
                           SPAN_NOME = ?,
                           DESCRICAO = ?,
                           TEXTO_BANNER_PRINCIPAL = ?,
                           TEXTO_BANNER_SECUNDARIO = ?,
                           FONTE_COR = ?,
                           COR_PRIMARIA = ?,
                           COR_SECUNDARIA = ?,
                           COR_TERCIARIA = ?,
                           FONTE_TEXTO = ?,
                           FONTE_TITULO = ?,
                           FONTE_LOGO = ?
                       WHERE ID_EMPRESAS = ?""",
                       (nome, span_nome, descricao, texto_banner_principal, texto_banner_secundario,
                        fonte_cor, cor_primaria, cor_secundaria, cor_terciaria,
                        fonte_texto, fonte_titulo, fonte_logo, id_empresa))

        con.commit()

        # Salvar imagens
        if logo:
            nome_imagem_logo = f'logo_{id_empresa}.jpeg'
            caminho_imagem_destino_logo = os.path.join(app.config['UPLOAD_FOLDER'], "Empresas")
            os.makedirs(caminho_imagem_destino_logo, exist_ok=True)
            logo.save(os.path.join(caminho_imagem_destino_logo, nome_imagem_logo))

        if banner:
            nome_imagem_banner = f'banner_{id_empresa}.jpeg'
            caminho_imagem_destino_banner = os.path.join(app.config['UPLOAD_FOLDER'], "Empresas")
            os.makedirs(caminho_imagem_destino_banner, exist_ok=True)
            banner.save(os.path.join(caminho_imagem_destino_banner, nome_imagem_banner))

        return jsonify({'message': "Configurações salvas com sucesso!"}), 200

    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/redefinir', methods=['POST'])
def redefinir():
    con = conexao()
    cur = con.cursor()
    try:
        # Verifica se o token existe
        if decodificar_token() == False:
            return jsonify({'error': 'Token necessário'}), 401

        if decodificar_token()['tipo'] != 0:
            return jsonify({'error': 'Token necessário'}), 401

        id_empresa = 1
        nome = "Doar"
        span_nome = "+"
        descricao = "A Doar+ é um portal solidário que conecta pessoas, campanhas e instituições em todo o Brasil, facilitando doações seguras e transparentes."
        texto_banner_principal = "Venha fazer a diferença e encontrar quem também faz!"
        texto_banner_secundario = "Sempre quis contribuir mais nunca soube como? Acesse a Doar+ e doe agora!"
        fonte_cor = "#1f1f1f"
        cor_primaria = "#167cbf"
        cor_secundaria = "#f65682"
        cor_terciaria = "#f7b567"
        fonte_logo = "Playwrite US Trad"
        fonte_texto = "Inter"
        fonte_titulo = "Inter"

        # Atualiza os dados do usuário no banco
        cur.execute("""UPDATE EMPRESAS
        SET NOME = ?,
        SPAN_NOME = ?,
        DESCRICAO = ?,
        TEXTO_BANNER_PRINCIPAL = ?,
        TEXTO_BANNER_SECUNDARIO = ?,
        FONTE_COR = ?,
        COR_PRIMARIA = ?,
        COR_SECUNDARIA = ?,
        COR_TERCIARIA = ?,
        FONTE_TEXTO = ?,
        FONTE_TITULO = ?,
        FONTE_LOGO = ?
        WHERE ID_EMPRESAS = ?""", (nome, span_nome, descricao, texto_banner_principal, texto_banner_secundario,
        fonte_cor, cor_primaria, cor_secundaria, cor_terciaria,
        fonte_texto, fonte_titulo, fonte_logo, id_empresa))

        # Confirma a alteração no banco
        con.commit()


        caminho_imagem = os.path.join(app.config['UPLOAD_FOLDER'], "Empresas")

        caminho_imagem_logo = os.path.join(caminho_imagem, f'logo_{id_empresa}.jpeg')
        caminho_completo_banner = os.path.join(caminho_imagem, f'banner_{id_empresa}.jpeg')

        if os.path.exists(caminho_imagem_logo):
            os.remove(caminho_imagem_logo)

        if os.path.exists(caminho_completo_banner):
            os.remove(caminho_completo_banner)

        # Retorna sucesso
        return jsonify({'message': "Empresa redefinida com sucesso",
        'empresa': {
        'nome': nome,
        'span_nome': span_nome,
        'descricao': descricao,
        'texto_banner_principal': texto_banner_principal,
        'texto_banner_secundario': texto_banner_secundario,
        'cor_primaria': cor_primaria,
        'cor_secundaria': cor_secundaria,
        'cor_terceria': cor_terciaria,
        'fonte_texto': fonte_texto,
        'fonte_titulo': fonte_titulo,
        'fonte_cor': fonte_cor,
        'fonte-logo': fonte_logo,
        'logo': f'logo_{id_empresa}.jpeg',
        'banner': f'banner_{id_empresa}.jpeg'
        }
        }), 201

    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/criar_story', methods=['POST'])
def criar_story():
    token_data = decodificar_token()

    if token_data == False:
        return jsonify({'error': 'Token necessário. Faça login novamente.'}), 401

    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem criar stories'}), 403

    texto = request.form.get('texto', '')
    arquivo = request.files.get('arquivos')

    if not texto:
        return jsonify({'error': 'O texto do story é obrigatório'}), 400

    if not arquivo:
        return jsonify({'error': 'Selecione uma imagem ou vídeo para o story'}), 400

    con = conexao()
    cur = con.cursor()

    try:
        # Inserir story
        cur.execute("""
            INSERT INTO STORIES (ID_USUARIOS, TEXTO, DATA_CRIACAO, VISIVEL)
            VALUES (?, ?, ?, ?) RETURNING ID_STORIES
        """, (token_data['id_usuarios'], texto, datetime.datetime.now(), 1))

        id_story = cur.fetchone()[0]

        # Salvar arquivo
        extensao = arquivo.filename.split('.')[-1]
        nome_arquivo = f'{id_story}_{random.randint(1, 99999)}.{extensao}'

        pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'Stories')
        os.makedirs(pasta, exist_ok=True)

        caminho = os.path.join(pasta, nome_arquivo)
        arquivo.save(caminho)

        # Inserir arquivo
        cur.execute("""
            INSERT INTO STORIES_ARQUIVOS (ID_STORIES, ARQUIVO)
            VALUES (?, ?)
        """, (id_story, nome_arquivo))

        con.commit()

        return jsonify({'message': 'Story criado com sucesso!', 'story_id': id_story}), 201

    except Exception as e:
        con.rollback()
        print(f"ERRO criar_story: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/feed_stories', methods=['GET'])
def feed_stories():
    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT
                s.ID_STORIES,
                s.TEXTO,
                s.DATA_CRIACAO,
                u.ID_USUARIOS,
                u.NOME,
                sa.ARQUIVO
            FROM STORIES s
            INNER JOIN USUARIOS u ON u.ID_USUARIOS = s.ID_USUARIOS
            LEFT JOIN STORIES_ARQUIVOS sa ON sa.ID_STORIES = s.ID_STORIES
            WHERE s.DATA_CRIACAO >= DATEADD(-1 DAY TO CURRENT_TIMESTAMP)
                AND s.VISIVEL = 1
                AND u.APROVACAO = 1
                AND u.ATIVO = 1
            ORDER BY s.DATA_CRIACAO DESC
        """)

        dados = cur.fetchall()

        stories_dict = {}

        for s in dados:
            id_story = s[0]
            texto = s[1] if s[1] else ''
            ong_id = s[3]
            ong_nome = s[4]
            arquivo = s[5] if len(s) > 5 else None

            if ong_id not in stories_dict:
                stories_dict[ong_id] = {
                    'ong_id': ong_id,
                    'ong_nome': ong_nome,
                    'ong_foto': f'{ong_id}.jpeg',
                    'stories': []
                }

            if arquivo:
                stories_dict[ong_id]['stories'].append({
                    'id': id_story,
                    'texto': texto,
                    'arquivo': arquivo
                })

        # Converter dicionário para lista
        stories_lista = list(stories_dict.values())

        return jsonify({'stories': stories_lista}), 200

    except Exception as e:
        print(f"ERRO feed_stories: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/listar_stories', methods=['GET'])
def listar_stories():
    token_data = decodificar_token()

    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT
                s.ID_STORIES,
                sa.ARQUIVO,
                s.DATA_CRIACAO,
                s.TEXTO
            FROM STORIES s
            LEFT JOIN STORIES_ARQUIVOS sa ON sa.ID_STORIES = s.ID_STORIES
            WHERE s.ID_USUARIOS = ?
            ORDER BY s.DATA_CRIACAO DESC
        """, (token_data['id_usuarios'],))

        stories = []
        for item in cur.fetchall():
            stories.append({
                'id': item[0],
                'arquivo': item[1],
                'data': item[2].strftime('%d/%m/%Y %H:%M') if item[2] else '',
                'texto': item[3] if item[3] else ''
            })

        return jsonify({'stories': stories}), 200

    except Exception as e:
        print(f"ERRO listar_stories: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/deletar_story/<int:id_story>', methods=['DELETE'])
def deletar_story(id_story):
    token_data = decodificar_token()

    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        # Verificar se o story pertence ao usuário
        cur.execute("""
            SELECT ID_USUARIOS FROM STORIES WHERE ID_STORIES = ?
        """, (id_story,))
        story = cur.fetchone()

        if not story:
            return jsonify({'error': 'Story não encontrado'}), 404

        if story[0] != token_data['id_usuarios'] and token_data['tipo'] != 0:
            return jsonify({'error': 'Sem permissão para deletar este story'}), 403

        # Buscar arquivos do story
        cur.execute("SELECT ARQUIVO FROM STORIES_ARQUIVOS WHERE ID_STORIES = ?", (id_story,))
        arquivos = cur.fetchall()

        # Deletar arquivos físicos
        pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'Stories')
        for arquivo in arquivos:
            if arquivo[0]:
                caminho = os.path.join(pasta, arquivo[0])
                if os.path.exists(caminho):
                    os.remove(caminho)

        # Deletar registros do banco
        cur.execute("DELETE FROM STORIES_ARQUIVOS WHERE ID_STORIES = ?", (id_story,))
        cur.execute("DELETE FROM STORIES WHERE ID_STORIES = ?", (id_story,))
        con.commit()

        return jsonify({'message': 'Story deletado com sucesso'}), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO deletar_story: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# Buscar um usuário específico pelo ID (usado para carregar dados nas telas de Edição)
@app.route('/buscar_usuario_id/<int:id_usuarios>', methods=['GET'])
def buscar_usuario_id(id_usuarios):
    # Verifica token passado pela URL (?token=...)
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        # Busca o usuário pelo ID exato recebido na URL
        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL, TELEFONE, TIPO
                       FROM USUARIOS 
                       WHERE ID_USUARIOS = ?""", (id_usuarios,))

        usuario = cur.fetchone()

        if not usuario:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Monta o objeto com os dados mapeados das colunas
        usuario_data = {
            "id_usuarios": usuario[0],
            "nome": usuario[1],
            "email": usuario[2],
            "telefone": usuario[3],
            "tipo": usuario[4]
        }

        # Retorna o objeto dentro de 'usuario' para o React ler corretamente
        return jsonify({"usuario": usuario_data}), 200

    except Exception as e:
        return jsonify({'message': f'Erro ao consultar o banco de dados: {e}'}), 500
    finally:
        cur.close()
        con.close()