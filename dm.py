# dm.py
from flask import jsonify, request
from main import app, socketio
from db import conexao
from funcao import decodificar_token
from datetime import datetime
from flask_socketio import emit, join_room, leave_room

# Dicionário para armazenar conexões dos usuários (id_usuario -> sid)
conexoes_usuarios = {}


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
        # Verificar se a ONG existe
        cur.execute("""
            SELECT ID_USUARIOS FROM USUARIOS
            WHERE ID_USUARIOS = ? AND TIPO = 2 AND ATIVO = 1 AND APROVACAO = 1
        """, (id_ong,))
        ong = cur.fetchone()

        if not ong:
            return jsonify({'error': 'ONG não encontrada'}), 404

        # Verificar se já existe conversa
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

        # Criar nova conversa
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
        # Verificar conversa
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

        # Salvar mensagem
        cur.execute("""
            INSERT INTO MENSAGENS (ID_CONVERSA, ID_REMETENTE, MENSAGEM, DATA_ENVIO) 
            VALUES (?, ?, ?, ?) RETURNING ID_MENSAGEM
        """, (id_conversa, id_remetente, mensagem_texto, datetime.now()))

        novo_id = cur.fetchone()[0]

        # Atualizar última mensagem
        cur.execute("""
            UPDATE CONVERSAS SET ULTIMA_MENSAGEM = ? WHERE ID_CONVERSA = ?
        """, (datetime.now(), id_conversa))

        con.commit()

        # Buscar dados do remetente
        cur.execute("SELECT NOME FROM USUARIOS WHERE ID_USUARIOS = ?", (id_remetente,))
        remetente = cur.fetchone()
        nome_remetente = remetente[0] if remetente else 'Usuário'

        data_envio = datetime.now().strftime('%d/%m/%Y %H:%M')

        mensagem_data = {
            'id': novo_id,
            'conversa_id': id_conversa,
            'remetente_id': id_remetente,
            'remetente_nome': nome_remetente,
            'mensagem': mensagem_texto,
            'data': data_envio
        }

        # Enviar para a sala da conversa via socket
        sala = f"conversa_{id_conversa}"
        socketio.emit('new_message', mensagem_data, room=sala)

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
        if tipo_usuario == 1:  # Doador
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
        else:  # ONG
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

            # Buscar última mensagem
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


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


# ==================== SOCKET.IO EVENTOS ====================

@socketio.on('connect')
def handle_connect():
    print(f'Cliente conectado: {request.sid}')


@socketio.on('disconnect')
def handle_disconnect():
    # Remover usuário do dicionário de conexões
    usuario_id = None
    for uid, sid in conexoes_usuarios.items():
        if sid == request.sid:
            usuario_id = uid
            break

    if usuario_id:
        del conexoes_usuarios[usuario_id]
        print(f'Usuário {usuario_id} desconectado')

    print(f'Cliente desconectado: {request.sid}')


@socketio.on('authenticate')
def handle_authenticate(data):
    token = data.get('token')
    if not token:
        emit('error', {'error': 'Token não fornecido'})
        return

    token_data = decodificar_token(token)
    if token_data == False:
        emit('error', {'error': 'Token inválido'})
        return

    usuario_id = token_data['id_usuarios']
    conexoes_usuarios[usuario_id] = request.sid

    print(f'Usuário {usuario_id} autenticado')

    # Entrar nas salas das conversas
    con = conexao()
    cur = con.cursor()

    try:
        tipo = token_data['tipo']
        if tipo == 1:
            cur.execute("SELECT ID_CONVERSA FROM CONVERSAS WHERE ID_DOADOR = ?", (usuario_id,))
        else:
            cur.execute("SELECT ID_CONVERSA FROM CONVERSAS WHERE ID_ONG = ?", (usuario_id,))

        conversas = cur.fetchall()
        for conv in conversas:
            sala = f"conversa_{conv[0]}"
            join_room(sala)
            print(f'Usuário {usuario_id} entrou na sala {sala}')
    except Exception as e:
        print(f'Erro ao entrar nas salas: {e}')
    finally:
        cur.close()
        con.close()

    emit('authenticated', {'status': 'ok', 'usuario_id': usuario_id})


@socketio.on('join_conversa')
def handle_join_conversa(data):
    conversa_id = data.get('conversa_id')
    if conversa_id:
        sala = f"conversa_{conversa_id}"
        join_room(sala)
        print(f'Cliente {request.sid} entrou na sala {sala}')
        emit('joined_conversa', {'conversa_id': conversa_id})


@socketio.on('leave_conversa')
def handle_leave_conversa(data):
    conversa_id = data.get('conversa_id')
    if conversa_id:
        sala = f"conversa_{conversa_id}"
        leave_room(sala)
        print(f'Cliente {request.sid} saiu da sala {sala}')


@socketio.on('send_message')
def handle_send_message(data):
    token = data.get('token')
    if not token:
        emit('error', {'error': 'Token não fornecido'})
        return

    token_data = decodificar_token(token)
    if token_data == False:
        emit('error', {'error': 'Token inválido'})
        return

    conversa_id = data.get('conversa_id')
    mensagem_texto = data.get('mensagem', '').strip()
    id_remetente = token_data['id_usuarios']

    if not mensagem_texto or not conversa_id:
        emit('error', {'error': 'Dados inválidos'})
        return

    con = conexao()
    cur = con.cursor()

    try:
        # Verificar conversa
        cur.execute("""
            SELECT ID_DOADOR, ID_ONG FROM CONVERSAS WHERE ID_CONVERSA = ?
        """, (conversa_id,))
        conversa = cur.fetchone()

        if not conversa:
            emit('error', {'error': 'Conversa não encontrada'})
            return

        id_doador = conversa[0]
        id_ong = conversa[1]

        if id_remetente != id_doador and id_remetente != id_ong:
            emit('error', {'error': 'Você não participa desta conversa'})
            return

        # Salvar mensagem
        cur.execute("""
            INSERT INTO MENSAGENS (ID_CONVERSA, ID_REMETENTE, MENSAGEM, DATA_ENVIO) 
            VALUES (?, ?, ?, ?) RETURNING ID_MENSAGEM
        """, (conversa_id, id_remetente, mensagem_texto, datetime.now()))

        novo_id = cur.fetchone()[0]

        # Atualizar última mensagem
        cur.execute("""
            UPDATE CONVERSAS SET ULTIMA_MENSAGEM = ? WHERE ID_CONVERSA = ?
        """, (datetime.now(), conversa_id))

        con.commit()

        # Buscar dados do remetente
        cur.execute("SELECT NOME FROM USUARIOS WHERE ID_USUARIOS = ?", (id_remetente,))
        remetente = cur.fetchone()
        nome_remetente = remetente[0] if remetente else 'Usuário'

        data_envio = datetime.now().strftime('%d/%m/%Y %H:%M')

        mensagem_data = {
            'id': novo_id,
            'conversa_id': conversa_id,
            'remetente_id': id_remetente,
            'remetente_nome': nome_remetente,
            'mensagem': mensagem_texto,
            'data': data_envio
        }

        sala = f"conversa_{conversa_id}"
        emit('new_message', mensagem_data, room=sala)

    except Exception as e:
        con.rollback()
        print(f'Erro ao enviar mensagem via socket: {e}')
        import traceback
        traceback.print_exc()
        emit('error', {'error': str(e)})
    finally:
        cur.close()
        con.close()