from flask import jsonify, request
from main import app
from db import conexao
from funcao import decodificar_token
from datetime import datetime


# ============================================
# CRIAR CONVERSA OU PEGAR JÁ EXISTENTE
# ============================================
@app.route('/dm/iniciar_conversa/<int:id_ong>', methods=['POST'])
def iniciar_conversa(id_ong):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    if token_data['tipo'] != 1:
        return jsonify({'error': 'Apenas doadores podem iniciar conversa'}), 403

    id_doador = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT ID_USUARIOS FROM USUARIOS
            WHERE ID_USUARIOS = ? AND TIPO = 2 AND ATIVO = 1 AND APROVACAO = 1
        """, (id_ong,))

        ong = cur.fetchone()

        if not ong:
            return jsonify({'error': 'ONG não encontrada'}), 404

        cur.execute("""
            SELECT ID_CONVERSA FROM CONVERSAS
            WHERE ID_DOADOR = ? AND ID_ONG = ?
        """, (id_doador, id_ong))

        conversa = cur.fetchone()

        if conversa:
            return jsonify({
                'message': 'Conversa já existe',
                'conversa_id': conversa[0]
            }), 200

        # Não inserir ID manualmente, deixar o IDENTITY gerar
        cur.execute("""
            INSERT INTO CONVERSAS (ID_DOADOR, ID_ONG, ULTIMA_MENSAGEM) 
            VALUES (?, ?, ?) RETURNING ID_CONVERSA
        """, (id_doador, id_ong, datetime.now()))

        novo_id = cur.fetchone()[0]
        con.commit()

        return jsonify({
            "message": 'Conversa iniciada com sucesso',
            'conversa_id': novo_id
        }), 201

    except Exception as e:
        con.rollback()
        print(f'Erro: {e}')
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ENVIAR MENSAGEM
# ============================================
@app.route('/dm/enviar_mensagem/<int:id_conversa>', methods=['POST'])
def enviar_mensagem(id_conversa):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    id_remetente = token_data['id_usuarios']

    data = request.get_json()
    mensagem_texto = data.get('mensagem', '').strip()

    if not mensagem_texto:
        return jsonify({'error': 'Mensagem não pode estar vazia'}), 400

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT ID_DOADOR, ID_ONG FROM CONVERSAS WHERE ID_CONVERSA = ?
        """, (id_conversa,))

        conversa = cur.fetchone()

        if not conversa:
            return jsonify({'error': 'Conversa não encontrada'}), 404

        id_doador = conversa[0]
        id_ong = conversa[1]

        if id_remetente != id_doador and id_remetente != id_ong:
            return jsonify({'error': 'Você não participa desta conversa'}), 403

        # Não inserir ID manualmente, deixar o IDENTITY gerar
        cur.execute("""
            INSERT INTO MENSAGENS (ID_CONVERSA, ID_REMETENTE, MENSAGEM, DATA_ENVIO) 
            VALUES (?, ?, ?, ?) RETURNING ID_MENSAGEM
        """, (id_conversa, id_remetente, mensagem_texto, datetime.now()))

        resultado = cur.fetchone()

        if resultado:
            novo_id = resultado[0]
        else:
            # Se não retornar ID, buscar o último inserido
            cur.execute("SELECT GEN_ID(GEN_MENSAGENS, 0) FROM RDB$DATABASE")
            novo_id = cur.fetchone()[0]

        cur.execute("""
            UPDATE CONVERSAS SET ULTIMA_MENSAGEM = ? WHERE ID_CONVERSA = ?
        """, (datetime.now(), id_conversa))

        con.commit()

        return jsonify({
            'message': 'Mensagem enviada com sucesso',
            'mensagem_id': novo_id
        }), 201

    except Exception as e:
        con.rollback()
        print(f'Erro: {e}')
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# LISTAR CONVERSAS DO USUÁRIO
# ============================================
@app.route('/dm/listar_conversas', methods=['GET'])
def listar_conversas():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    id_usuario = token_data['id_usuarios']
    tipo_usuario = token_data['tipo']

    con = conexao()
    cur = con.cursor()

    try:
        if tipo_usuario == 1:
            cur.execute("""
                SELECT 
                    c.ID_CONVERSA,
                    c.ID_ONG,
                    u.NOME,
                    c.ULTIMA_MENSAGEM
                FROM CONVERSAS c
                INNER JOIN USUARIOS u ON u.ID_USUARIOS = c.ID_ONG
                WHERE c.ID_DOADOR = ?
                ORDER BY c.ULTIMA_MENSAGEM DESC
            """, (id_usuario,))
        else:
            cur.execute("""
                SELECT 
                    c.ID_CONVERSA,
                    c.ID_DOADOR,
                    u.NOME,
                    c.ULTIMA_MENSAGEM
                FROM CONVERSAS c
                INNER JOIN USUARIOS u ON u.ID_USUARIOS = c.ID_DOADOR
                WHERE c.ID_ONG = ?
                ORDER BY c.ULTIMA_MENSAGEM DESC
            """, (id_usuario,))

        conversas = cur.fetchall()

        lista_conversas = []
        for conv in conversas:
            data_ultima = ''
            if conv[3]:
                try:
                    data_ultima = conv[3].strftime('%d/%m/%Y %H:%M')
                except:
                    data_ultima = str(conv[3])

            cur.execute("""
                SELECT FIRST 1 MENSAGEM FROM MENSAGENS 
                WHERE ID_CONVERSA = ? 
                ORDER BY DATA_ENVIO DESC
            """, (conv[0],))
            ultima_msg = cur.fetchone()

            lista_conversas.append({
                'conversa_id': conv[0],
                'usuario_id': conv[1],
                'usuario_nome': conv[2],
                'usuario_foto': f'{conv[1]}.jpeg',
                'ultima_mensagem': data_ultima,
                'ultimo_texto': ultima_msg[0] if ultima_msg else ''
            })

        return jsonify({'conversas': lista_conversas}), 200

    except Exception as e:
        print(f"ERRO listar_conversas: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# BUSCAR MENSAGENS DE UMA CONVERSA
# ============================================
@app.route('/dm/mensagens/<int:id_conversa>', methods=['GET'])
def buscar_mensagens(id_conversa):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    id_usuario = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT ID_DOADOR, ID_ONG FROM CONVERSAS WHERE ID_CONVERSA = ?
        """, (id_conversa,))
        conversa = cur.fetchone()

        if not conversa:
            return jsonify({'error': 'Conversa não encontrada'}), 404

        if id_usuario != conversa[0] and id_usuario != conversa[1]:
            return jsonify({'error': 'Acesso negado'}), 403

        cur.execute("""
            SELECT 
                ID_MENSAGEM,
                ID_REMETENTE,
                MENSAGEM,
                DATA_ENVIO
            FROM MENSAGENS
            WHERE ID_CONVERSA = ?
            ORDER BY DATA_ENVIO ASC
        """, (id_conversa,))

        mensagens = cur.fetchall()

        lista_mensagens = []
        for msg in mensagens:
            data_envio = ''
            if msg[3]:
                try:
                    data_envio = msg[3].strftime('%d/%m/%Y %H:%M')
                except:
                    data_envio = str(msg[3])

            lista_mensagens.append({
                'id': msg[0],
                'remetente_id': msg[1],
                'mensagem': msg[2],
                'data': data_envio,
                'is_meu_envio': msg[1] == id_usuario
            })

        return jsonify({'mensagens': lista_mensagens}), 200

    except Exception as e:
        print(f"ERRO buscar_mensagens: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# VERIFICAR SE EXISTE CONVERSA COM ONG
# ============================================
@app.route('/dm/verificar_conversa/<int:id_ong>', methods=['GET'])
def verificar_conversa(id_ong):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    if token_data['tipo'] != 1:
        return jsonify({'error': 'Apenas doadores podem acessar'}), 403

    id_doador = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT ID_CONVERSA FROM CONVERSAS 
            WHERE ID_DOADOR = ? AND ID_ONG = ?
        """, (id_doador, id_ong))
        conversa = cur.fetchone()

        return jsonify({
            'existe': conversa is not None,
            'conversa_id': conversa[0] if conversa else None
        }), 200

    except Exception as e:
        print(f"ERRO verificar_conversa: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# LISTAR ONGS ATIVAS PARA CONVERSAR
# ============================================
@app.route('/listar_ongs_ativas', methods=['GET'])
def listar_ongs_ativas():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT ID_USUARIOS, NOME, CATEGORIA, LOCALIZACAO
            FROM USUARIOS
            WHERE TIPO = 2 AND ATIVO = 1 AND APROVACAO = 1
            ORDER BY NOME ASC
        """)

        ongs = cur.fetchall()

        lista_ongs = []
        for ong in ongs:
            lista_ongs.append({
                'id': ong[0],
                'nome': ong[1],
                'categoria': ong[2] if ong[2] else '',
                'localizacao': ong[3] if ong[3] else ''
            })

        return jsonify({'ongs': lista_ongs}), 200

    except Exception as e:
        print(f"ERRO listar_ongs_ativas: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()