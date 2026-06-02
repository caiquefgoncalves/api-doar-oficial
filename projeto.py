# projeto.py CORRIGIDO
from flask import jsonify, request, render_template
from main import app
from db import conexao
from funcao import decodificar_token, gerar_qr_pix, enviando_email
import os
from datetime import datetime
import threading


@app.route('/criar_projeto', methods=['POST'])
def criar_projeto():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem criar projetos'}), 403

    titulo = request.form.get('titulo', None)
    descricao = request.form.get('descricao', None)
    categoria = request.form.get('categoria', None)
    tipo_ajuda = request.form.get('tipo_ajuda', None)
    localizacao = request.form.get('localizacao', None)
    status = request.form.get('status', 'Ativo')
    foto_projeto = request.files.get('foto')

    id_usuarios = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        if not titulo or titulo.strip() == '':
            return jsonify({"error": "Título é obrigatório"}), 400
        if not descricao or descricao.strip() == '':
            return jsonify({"error": "Descrição é obrigatória"}), 400
        if not categoria:
            return jsonify({'error': 'Escolha uma categoria'}), 400
        if not tipo_ajuda:
            return jsonify({"error": "Escolha um tipo de ajuda"}), 400

        cur.execute("""INSERT INTO PROJETOS (ID_USUARIOS, TITULO, DESCRICAO, CATEGORIA, 
                                             STATUS, TIPO_AJUDA, LOCALIZACAO)
                       VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING ID_PROJETOS""",
                    (id_usuarios, titulo, descricao, categoria, status, tipo_ajuda, localizacao))

        id_projetos = cur.fetchone()[0]
        con.commit()

        if foto_projeto:
            try:
                nome_imagem = f'{id_projetos}.jpeg'
                caminho_destino = os.path.join(app.config['UPLOAD_FOLDER'], 'Projetos')
                os.makedirs(caminho_destino, exist_ok=True)
                foto_projeto.save(os.path.join(caminho_destino, nome_imagem))
            except Exception as e:
                print(f"Erro ao salvar foto: {e}")

        return jsonify({'message': "Projeto cadastrado com sucesso!", 'id': id_projetos}), 201
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Listar projetos da ONG logada
# ============================================
@app.route('/listar_projetos', methods=['GET'])
def listar_projetos_ong():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    id_usuarios = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        if token_data['tipo'] == 2:
            # ONG vê apenas seus projetos
            cur.execute("""SELECT ID_PROJETOS, ID_USUARIOS, TITULO, DESCRICAO, CATEGORIA, 
                                  STATUS, TIPO_AJUDA, LOCALIZACAO
                           FROM PROJETOS WHERE ID_USUARIOS = ? ORDER BY ID_PROJETOS DESC""", (id_usuarios,))
        else:
            # Outros veem todos os projetos
            cur.execute("""SELECT ID_PROJETOS, ID_USUARIOS, TITULO, DESCRICAO, CATEGORIA, 
                                  STATUS, TIPO_AJUDA, LOCALIZACAO
                           FROM PROJETOS ORDER BY ID_PROJETOS DESC""")

        projetos = cur.fetchall()

        lista_projetos = []
        for p in projetos:

            lista_projetos.append({
                'id': p[0],
                'id_usuarios': p[1],
                'titulo': p[2],
                'descricao': p[3],
                'categoria': p[4],
                'status': p[5],
                'tipo_ajuda': p[6],
                'localizacao': p[7],
                'foto': f'{p[0]}.jpeg'
            })

        return jsonify({'projetos': lista_projetos}), 200
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Buscar projeto por ID
# ============================================
@app.route('/buscar_projeto/<int:id_projetos>', methods=['GET'])
def buscar_projeto(id_projetos):
    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""SELECT ID_PROJETOS, ID_USUARIOS, TITULO, DESCRICAO, CATEGORIA, 
                              STATUS, TIPO_AJUDA, LOCALIZACAO
                       FROM PROJETOS WHERE ID_PROJETOS = ?""", (id_projetos,))
        p = cur.fetchone()

        if not p:
            return jsonify({"error": "Projeto não encontrado"}), 404

        return jsonify({'projeto': {
            'id': p[0], 'id_usuarios': p[1], 'titulo': p[2], 'descricao': p[3],
            'categoria': p[4], 'status': p[5], 'tipo_ajuda': p[6], 'localizacao': p[7]
        }}), 200
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Editar projeto
# ============================================
@app.route('/editar_projeto/<int:id_projetos>', methods=['PUT'])
def editar_projeto(id_projetos):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("SELECT ID_USUARIOS FROM PROJETOS WHERE ID_PROJETOS = ?", (id_projetos,))
        projeto = cur.fetchone()
        if not projeto:
            return jsonify({"error": "Projeto não encontrado"}), 404

        # Só dono ou ADM pode editar
        if token_data['tipo'] != 0 and token_data['id_usuarios'] != projeto[0]:
            return jsonify({'error': 'Sem permissão'}), 403

        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        categoria = request.form.get('categoria')
        tipo_ajuda = request.form.get('tipo_ajuda')
        localizacao = request.form.get('localizacao')
        status = request.form.get('status')
        foto_projeto = request.files.get('foto')

        cur.execute("""UPDATE PROJETOS SET TITULO = ?, DESCRICAO = ?, CATEGORIA = ?,
                       STATUS = ?, TIPO_AJUDA = ?, LOCALIZACAO = ?
                       WHERE ID_PROJETOS = ?""",
                    (titulo, descricao, categoria, status, tipo_ajuda, localizacao, id_projetos))
        con.commit()

        if foto_projeto:
            try:
                nome_imagem = f'{id_projetos}.jpeg'
                caminho_destino = os.path.join(app.config['UPLOAD_FOLDER'], 'Projetos')
                os.makedirs(caminho_destino, exist_ok=True)
                foto_projeto.save(os.path.join(caminho_destino, nome_imagem))
            except Exception as e:
                print(f"Erro ao salvar foto: {e}")

        return jsonify({'message': 'Projeto editado com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Deletar projeto
# ============================================
@app.route('/deletar_projeto/<int:id_projetos>', methods=['DELETE'])
def deletar_projeto(id_projetos):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("SELECT ID_USUARIOS FROM PROJETOS WHERE ID_PROJETOS = ?", (id_projetos,))
        projeto = cur.fetchone()
        if not projeto:
            return jsonify({"error": "Projeto não encontrado"}), 404

        if token_data['tipo'] != 0 and token_data['id_usuarios'] != projeto[0]:
            return jsonify({'error': 'Sem permissão'}), 403

        cur.execute("DELETE FROM ATUALIZACOES WHERE ID_PROJETOS = ?", (id_projetos,))
        cur.execute("DELETE FROM PROJETOS WHERE ID_PROJETOS = ?", (id_projetos,))
        con.commit()

        return jsonify({'message': 'Projeto excluído com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/ver_projeto_publico/<int:id_projetos>', methods=['GET'])
def ver_projeto_publico(id_projetos):
    con = conexao()
    cur = con.cursor()
    try:
        # Busca o projeto
        cur.execute("""SELECT ID_PROJETOS, ID_USUARIOS, TITULO, DESCRICAO, CATEGORIA, 
                              STATUS, TIPO_AJUDA, LOCALIZACAO
                       FROM PROJETOS WHERE ID_PROJETOS = ?""", (id_projetos,))
        p = cur.fetchone()
        if not p:
            return jsonify({"error": "Projeto não encontrado"}), 404

        # Busca a ONG
        cur.execute("""SELECT ID_USUARIOS, NOME, DESCRICAO_BREVE, CPF_CNPJ, 
                              COD_BANCO, NUM_AGENCIA, LOCALIZACAO, CHAVE_PIX
                       FROM USUARIOS WHERE ID_USUARIOS = ?""", (p[1],))
        ong = cur.fetchone()

        # Formatar CNPJ
        cnpj_formatado = None
        if ong and ong[3]:
            cnpj = ong[3]
            if len(cnpj) == 14:
                cnpj_formatado = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
            elif len(cnpj) == 11:
                cnpj_formatado = f"{cnpj[:3]}.{cnpj[3:6]}.{cnpj[6:9]}-{cnpj[9:]}"
            else:
                cnpj_formatado = cnpj

        # Gerar QR Code PIX (apenas se a ONG tiver chave PIX)
        nome_qr = None
        chave_pix = None
        if ong and ong[7]:
            try:
                resultado = gerar_qr_pix(
                    chave_pix=ong[7],
                    nome=ong[1],
                    cidade=ong[6] if ong[6] else '',
                    id_ong=ong[0],
                    pasta_base=app.config['UPLOAD_FOLDER']
                )
                nome_qr = resultado[0]
                chave_pix = resultado[1]
            except Exception as e:
                print(f"Erro ao gerar QR Code: {e}")

        # Busca atualizações
        cur.execute("""SELECT ID_ATUALIZACOES, TITULO, TEXTO, DATA_CRIACAO
                       FROM ATUALIZACOES WHERE ID_PROJETOS = ? 
                       ORDER BY DATA_CRIACAO DESC""", (id_projetos,))
        atts = cur.fetchall()

        # Inicializar lista de atualizações
        atualizacoes_lista = []
        if atts:
            for a in atts:
                data_str = ''
                if a[3]:
                    try:
                        data_str = a[3].strftime('%d/%m/%Y %H:%M')
                    except:
                        data_str = str(a[3])
                atualizacoes_lista.append({
                    'id': a[0],
                    'titulo': str(a[1]) if a[1] else '',
                    'texto': str(a[2]) if a[2] else '',
                    'data': data_str,
                    'foto': f'{a[0]}.jpeg'
                })

        return jsonify({
            'projeto': {
                'id': p[0], 'id_usuarios': p[1], 'titulo': p[2], 'descricao': p[3],
                'categoria': p[4], 'status': p[5], 'tipo_ajuda': p[6], 'localizacao': p[7]
            },
            'ong': {
                'id': ong[0], 'nome': ong[1], 'descricao_breve': ong[2],
                'cpf_cnpj': cnpj_formatado, 'cod_banco': ong[4], 'num_agencia': ong[5],
                'localizacao': ong[6],
                'pix': nome_qr,
                'chave_pix': chave_pix
            } if ong else None,
            'qtd_atualizacoes': len(atualizacoes_lista),
            'atualizacoes': atualizacoes_lista
        }), 200
    except Exception as e:
        print(f"ERRO ver_projeto_publico: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/listar_projetos_publicos', methods=['GET'])
def listar_projetos_publicos():
    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT p.ID_PROJETOS, p.ID_USUARIOS, p.TITULO, p.DESCRICAO, p.CATEGORIA, 
                   p.STATUS, p.TIPO_AJUDA, p.LOCALIZACAO, u.NOME
            FROM PROJETOS p
            INNER JOIN USUARIOS u ON p.ID_USUARIOS = u.ID_USUARIOS
            WHERE u.APROVACAO = 1 AND u.ATIVO = 1 AND p.STATUS = 'Ativo'
            ORDER BY p.ID_PROJETOS DESC
        """)
        projetos = cur.fetchall()

        lista = []
        for p in projetos:
            if p[6] == "Dinheiro":
                tipo_ajuda = 0
            else:
                tipo_ajuda = 1
            lista.append({
                'id': p[0], 'id_usuarios': p[1], 'titulo': p[2], 'descricao': p[3],
                'categoria': p[4], 'status': p[5], 'tipo_ajuda': tipo_ajuda, 'localizacao': p[7],
                'ong_nome': p[8], 'foto': f'{p[0]}.jpeg'
            })

        return jsonify({'projetos': lista}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/doar_projeto/<int:id_projeto>', methods=['POST'])
def doar_projeto(id_projeto):
    con = conexao()
    cur = con.cursor()

    try:
        valor = request.json.get('valor')  # Agora vem como decimal (ex: 23.67)
        data = datetime.now()

        # Verifica token
        token_data = decodificar_token()

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado para doar'}), 401

        # Verifica se é doador (tipo 1)
        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem doar'}), 403

        id_doador = token_data['id_usuarios']

        # Buscar informações do doador
        cur.execute("SELECT NOME, EMAIL FROM USUARIOS WHERE ID_USUARIOS = ?", (id_doador,))
        doador = cur.fetchone()

        if not doador:
            return jsonify({'error': 'Doador não encontrado'}), 404

        nome_doador = doador[0]
        email_doador = doador[1]

        # Verifica se o projeto existe e está ativo
        cur.execute("""
            SELECT ID_PROJETOS, ID_USUARIOS, TITULO FROM PROJETOS
            WHERE ID_PROJETOS = ? AND STATUS = 'Ativo'
        """, (id_projeto,))

        projeto = cur.fetchone()

        if not projeto:
            return jsonify({'error': 'Projeto não encontrado ou não está disponível'}), 404

        id_ong = projeto[1]
        nome_projeto = projeto[2]

        # Buscar informações da ONG
        cur.execute("""
            SELECT ID_USUARIOS, NOME, LOCALIZACAO, CHAVE_PIX, EMAIL, MENSAGEM_AGRADECIMENTO
            FROM USUARIOS
            WHERE ID_USUARIOS = ? AND TIPO = 2 AND APROVACAO = 1
        """, (id_ong,))
        ong = cur.fetchone()

        if not ong:
            return jsonify({"error": "ONG não encontrada"}), 404

        chave_pix = ong[3]
        if not chave_pix or chave_pix.strip() == '':
            return jsonify({'error': 'Esta ONG não possui chave PIX cadastrada para receber doações'}), 400

        nome_ong = ong[1]
        cidade_ong = ong[2] if ong[2] else ''
        chave_pix = ong[3]
        email_ong = ong[4]
        mensagem_agradecimento = ong[5] if ong[
            5] else "Agradecemos imensamente por sua contribuição! Sua doação faz a diferença e nos ajuda a transformar vidas."

        # Criar nova doação - valor decimal
        cur.execute("""
            INSERT INTO DOACOES (ID_PROJETOS, ID_USUARIOS, VALOR, DATA_DOACAO)
            VALUES (?, ?, ?, ?) RETURNING ID_DOACOES
        """, (id_projeto, id_doador, valor, data))

        resultado = cur.fetchone()

        if resultado is None:
            return jsonify({'error': 'Erro ao registrar doação'}), 500

        id_doacao = resultado[0]

        con.commit()

        # Gerar QR Code PIX
        resultado_qr = gerar_qr_pix(
            chave_pix=chave_pix,
            nome=nome_ong,
            cidade=cidade_ong,
            id_ong=str(id_doacao),
            pasta_base=app.config['UPLOAD_FOLDER'],
            valor=str(valor),
            projeto=True
        )

        nome_qr = resultado_qr[0]
        chave_pix_formatada = resultado_qr[1]

        # Formatar valor para exibição
        valor_formatado = f"{float(valor):.2f}".replace('.', ',')
        data_formatada = data.strftime('%d/%m/%Y às %H:%M')

        # Envia e-mail para o doador
        if email_doador:
            assunto_doador = f"Obrigado por sua doação para {nome_ong}!"

            html_doador = render_template('email_doador_agradecimento.html',
                                          nome_doador=nome_doador,
                                          valor=valor_formatado,
                                          nome_projeto=nome_projeto,
                                          nome_ong=nome_ong,
                                          mensagem_agradecimento=mensagem_agradecimento
                                          )

            try:
                threading.Thread(target=enviando_email, args=(email_doador, assunto_doador, html_doador)).start()
                print(f"E-mail enviado para o doador: {email_doador}")
            except Exception as e:
                print(f"Erro ao enviar e-mail para doador: {e}")

        # Envia e-mail para a ONG
        if email_ong:
            assunto_ong = f"Nova doação recebida - {nome_doador} doou para {nome_projeto}"

            html_ong = render_template('email_ong_notificacao.html',
                                       nome_ong=nome_ong,
                                       valor=valor_formatado,
                                       nome_doador=nome_doador,
                                       nome_projeto=nome_projeto,
                                       data_doacao=data_formatada
                                       )

            try:
                threading.Thread(target=enviando_email, args=(email_ong, assunto_ong, html_ong)).start()
                print(f"E-mail enviado para a ONG: {email_ong}")
            except Exception as e:
                print(f"Erro ao enviar e-mail para ONG: {e}")

        return jsonify({
            'message': 'O QR code foi gerado com sucesso!',
            'pix': nome_qr,
            'chave_pix': chave_pix_formatada
        }), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO doar_projeto: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()

@app.route('/voluntario_projeto/<int:id_projeto>', methods=['POST'])
def voluntario_projeto(id_projeto):

    con = conexao()
    cur = con.cursor()

    try:
        mensagem = request.json.get('mensagem', '')
        data = datetime.now()

        # Verifica token
        token_data = decodificar_token()

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado para se voluntariar'}), 401

        # Verifica se é doador (tipo 1)
        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem se voluntariar'}), 403

        id_doador = token_data['id_usuarios']

        # Busca dados do doador
        cur.execute("SELECT NOME, EMAIL FROM USUARIOS WHERE ID_USUARIOS = ?", (id_doador,))
        doador = cur.fetchone()
        nome_doador = doador[0]
        email_doador = doador[1]

        # Verifica se o projeto existe e está ativo
        cur.execute("""
            SELECT ID_PROJETOS, ID_USUARIOS, TITULO FROM PROJETOS
            WHERE ID_PROJETOS = ? AND STATUS = 'Ativo'
        """, (id_projeto,))

        projeto = cur.fetchone()

        if not projeto:
            return jsonify({'error': 'Projeto não encontrado ou não está disponível'}), 404

        id_ong = projeto[1]
        nome_projeto = projeto[2]

        # Busca dados da ONG
        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL
        FROM USUARIOS
        WHERE ID_USUARIOS = ? AND TIPO = 2 AND APROVACAO = 1""", (id_ong,))
        ong = cur.fetchone()

        if not ong:
            return jsonify({"error": "ONG não encontrada"}), 404

        nome_ong = ong[1]
        email_ong = ong[2]

        # Criar novo voluntariado
        cur.execute("""
        INSERT INTO VOLUNTARIADO (ID_USUARIOS, ID_PROJETOS)
        VALUES (?, ?)
        """, (id_doador, id_projeto))
        con.commit()

        assunto = "Nova solicitação de voluntariado - Doar +"

        html = render_template('template_voluntariado.html',
            nome_ong=nome_ong,
            nome_usuario=nome_doador,
            email_usuario=email_doador,
            nome_projeto=nome_projeto,
            mensagem=mensagem
        )
        threading.Thread(target=enviando_email, args=(email_ong, assunto, html)).start()

        return jsonify({
            'message': f'O e-mail foi enviado com sucesso!',
        }), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO voluntario_projeto: {e}")
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/verificar_voluntario/<int:id_usuario>', methods=['GET'])
def verificar_voluntario(id_usuario):
    """Verifica se o usuário já se voluntariou em algum projeto"""
    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM VOLUNTARIADO 
            WHERE ID_USUARIOS = ?
        """, (id_usuario,))
        count = cur.fetchone()[0]

        return jsonify({
            'voluntario': count > 0
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()

@app.route('/verificar_voluntario_projeto/<int:id_projeto>', methods=['GET'])
def verificar_voluntario_projeto(id_projeto):
    """Verifica se o doador já se voluntariou nesse projeto específico"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 1:
        return jsonify({'voluntariou': False}), 200

    id_doador = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM VOLUNTARIADO 
            WHERE ID_USUARIOS = ? AND ID_PROJETOS = ?
        """, (id_doador, id_projeto))
        count = cur.fetchone()[0]

        return jsonify({'voluntariou': count > 0}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/gerar_qr_doacao/<int:id_projeto>', methods=['POST'])
def gerar_qr_doacao(id_projeto):
    """Apenas gera o QR Code sem registrar a doação no banco"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 1:
        return jsonify({'error': 'Apenas doadores podem gerar QR Code'}), 403

    valor = request.json.get('valor')

    if not valor or float(valor) <= 0:
        return jsonify({'error': 'Digite um valor válido'}), 400

    con = conexao()
    cur = con.cursor()

    try:
        # Buscar informações do projeto e ONG
        cur.execute("""
            SELECT p.ID_PROJETOS, p.ID_USUARIOS, p.TITULO, u.NOME, u.LOCALIZACAO, u.CHAVE_PIX
            FROM PROJETOS p
            INNER JOIN USUARIOS u ON p.ID_USUARIOS = u.ID_USUARIOS
            WHERE p.ID_PROJETOS = ? AND p.STATUS = 'Ativo'
        """, (id_projeto,))

        projeto = cur.fetchone()

        if not projeto:
            return jsonify({'error': 'Projeto não encontrado'}), 404

        id_ong = projeto[1]
        nome_projeto = projeto[2]
        nome_ong = projeto[3]
        cidade_ong = projeto[4] if projeto[4] else ''
        chave_pix = projeto[5]

        if not chave_pix or chave_pix.strip() == '':
            return jsonify({'error': 'Esta ONG não possui chave PIX cadastrada'}), 400

        # Gerar ID temporário para o QR Code (usando timestamp)
        id_temp = int(datetime.now().timestamp() * 1000)

        # Gerar QR Code PIX
        resultado_qr = gerar_qr_pix(
            chave_pix=chave_pix,
            nome=nome_ong,
            cidade=cidade_ong,
            id_ong=str(id_temp),
            pasta_base=app.config['UPLOAD_FOLDER'],
            valor=str(float(valor)),
            projeto=True
        )

        nome_qr = resultado_qr[0]
        chave_pix_formatada = resultado_qr[1]

        # Armazenar temporariamente os dados da doação em sessão ou retornar um token
        # Vamos retornar os dados necessários para o frontend

        return jsonify({
            'message': 'QR Code gerado com sucesso!',
            'pix': nome_qr,
            'chave_pix': chave_pix_formatada,
            'valor': valor,
            'id_projeto': id_projeto,
            'id_ong': id_ong,
            'nome_projeto': nome_projeto,
            'nome_ong': nome_ong
        }), 200

    except Exception as e:
        print(f"ERRO gerar_qr_doacao: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/confirmar_doacao', methods=['POST'])
def confirmar_doacao():
    """Confirma a doação após o pagamento"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 1:
        return jsonify({'error': 'Apenas doadores podem confirmar doação'}), 403

    data = request.get_json()
    id_projeto = data.get('id_projeto')
    valor = data.get('valor')
    id_ong = data.get('id_ong')
    nome_projeto = data.get('nome_projeto')
    nome_ong = data.get('nome_ong')

    if not id_projeto or not valor:
        return jsonify({'error': 'Dados incompletos'}), 400

    con = conexao()
    cur = con.cursor()

    try:
        id_doador = token_data['id_usuarios']
        data_doacao = datetime.now()

        # Buscar informações do doador
        cur.execute("SELECT NOME, EMAIL FROM USUARIOS WHERE ID_USUARIOS = ?", (id_doador,))
        doador = cur.fetchone()

        if not doador:
            return jsonify({'error': 'Doador não encontrado'}), 404

        nome_doador = doador[0]
        email_doador = doador[1]

        # Buscar informações da ONG
        cur.execute("""
            SELECT EMAIL, MENSAGEM_AGRADECIMENTO FROM USUARIOS WHERE ID_USUARIOS = ?
        """, (id_ong,))
        ong = cur.fetchone()

        if not ong:
            return jsonify({'error': 'ONG não encontrada'}), 404

        email_ong = ong[0]
        mensagem_agradecimento = ong[1] if ong[
            1] else "Agradecemos imensamente por sua contribuição! Sua doação faz a diferença e nos ajuda a transformar vidas."

        # Registrar doação no banco
        cur.execute("""
            INSERT INTO DOACOES (ID_PROJETOS, ID_USUARIOS, VALOR, DATA_DOACAO)
            VALUES (?, ?, ?, ?) RETURNING ID_DOACOES
        """, (id_projeto, id_doador, float(valor), data_doacao))

        id_doacao = cur.fetchone()[0]
        con.commit()

        # Formatar valor para exibição
        valor_formatado = f"{float(valor):.2f}".replace('.', ',')
        data_formatada = data_doacao.strftime('%d/%m/%Y às %H:%M')

        # Envia e-mail para o doador
        if email_doador:
            assunto_doador = f"Obrigado por sua doação para {nome_ong}!"
            html_doador = render_template('email_doador_agradecimento.html',
                                          nome_doador=nome_doador,
                                          valor=valor_formatado,
                                          nome_projeto=nome_projeto,
                                          nome_ong=nome_ong,
                                          mensagem_agradecimento=mensagem_agradecimento)
            threading.Thread(target=enviando_email, args=(email_doador, assunto_doador, html_doador)).start()

        # Envia e-mail para a ONG
        if email_ong:
            assunto_ong = f"Nova doação recebida - {nome_doador} doou para {nome_projeto}"
            html_ong = render_template('email_ong_notificacao.html',
                                       nome_ong=nome_ong,
                                       valor=valor_formatado,
                                       nome_doador=nome_doador,
                                       nome_projeto=nome_projeto,
                                       data_doacao=data_formatada)
            threading.Thread(target=enviando_email, args=(email_ong, assunto_ong, html_ong)).start()

        return jsonify({'message': 'Doação confirmada com sucesso!'}), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO confirmar_doacao: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()