# comentarios.py
from flask import jsonify, request
from main import app
from db import conexao
from funcao import decodificar_token
import datetime


# ============================================
# ROTAS DE COMENTÁRIOS
# ============================================

@app.route('/comentarios/<int:id_atualizacao>', methods=['GET', 'OPTIONS'])
def listar_comentarios(id_atualizacao):
    """Lista comentários de uma atualização"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        print(f"Buscando comentários da atualização {id_atualizacao}")

        # Buscar comentários com informações do usuário
        cur.execute("""
            SELECT FIRST 100
                c.ID_COMENTARIOS,
                c.ID_USUARIOS_DOADOR,
                c.TEXTO,
                c.DATA_CRIACAO,
                u.NOME,
                u.ID_USUARIOS
            FROM COMENTARIOS c
            INNER JOIN USUARIOS u ON c.ID_USUARIOS_DOADOR = u.ID_USUARIOS
            WHERE c.ID_ATUALIZACOES = ?
            ORDER BY c.DATA_CRIACAO ASC
        """, (id_atualizacao,))

        comentarios = cur.fetchall()
        print(f"Comentários encontrados: {len(comentarios) if comentarios else 0}")

        lista_comentarios = []
        if comentarios:
            for c in comentarios:
                # Formatar a data
                if c[3]:
                    if isinstance(c[3], str):
                        data_str = c[3]
                    else:
                        data_str = c[3].strftime('%d/%m/%Y %H:%M')
                else:
                    data_str = ''

                lista_comentarios.append({
                    'id': c[0],
                    'usuario_id': c[1],
                    'texto': c[2],
                    'data_criacao': data_str,
                    'usuario_nome': c[4] if c[4] else 'Usuário',
                    'usuario_foto': f'{c[5]}.jpeg' if c[5] else None
                })

        # Contar total de comentários
        cur.execute("""
            SELECT COUNT(*) FROM COMENTARIOS 
            WHERE ID_ATUALIZACOES = ?
        """, (id_atualizacao,))
        qtd = cur.fetchone()[0]

        return jsonify({
            'comentarios': lista_comentarios,
            'total': qtd
        }), 200

    except Exception as e:
        print(f"ERRO ao listar comentários: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/comentar/<int:id_atualizacao>', methods=['POST', 'OPTIONS'])
def comentar(id_atualizacao):
    """Doador comenta em uma atualização"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        print(f"Tentando comentar na atualização {id_atualizacao}")
        print(f"Headers: {dict(request.headers)}")
        print(f"Body: {request.get_data()}")

        # Verificar autenticação
        token_data = decodificar_token()
        print(f"Token data: {token_data}")

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado para comentar'}), 401

        # Verificar se é doador (tipo 1)
        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem comentar'}), 403

        id_doador = token_data['id_usuarios']
        print(f"Doador ID: {id_doador}")

        # Verificar se a atualização existe
        cur.execute("""
            SELECT ID_ATUALIZACOES FROM ATUALIZACOES 
            WHERE ID_ATUALIZACOES = ?
        """, (id_atualizacao,))
        atualizacao = cur.fetchone()

        if not atualizacao:
            return jsonify({'error': 'Atualização não encontrada'}), 404

        # Pegar texto do comentário
        data = request.get_json()
        print(f"Dados recebidos: {data}")

        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400

        texto = data.get('texto', '').strip()

        if not texto:
            return jsonify({'error': 'O comentário não pode estar vazio'}), 400

        if len(texto) > 255:
            return jsonify({'error': 'Comentário muito longo (máximo 255 caracteres)'}), 400

        # Data atual
        data_atual = datetime.datetime.now()

        # Inserir comentário
        cur.execute("""
            INSERT INTO COMENTARIOS (ID_USUARIOS_DOADOR, ID_ATUALIZACOES, TEXTO, DATA_CRIACAO)
            VALUES (?, ?, ?, ?)
        """, (id_doador, id_atualizacao, texto, data_atual))
        con.commit()
        print("Comentário inserido com sucesso!")

        # Buscar dados do usuário para retornar
        cur.execute("""
            SELECT NOME, ID_USUARIOS FROM USUARIOS 
            WHERE ID_USUARIOS = ?
        """, (id_doador,))
        usuario = cur.fetchone()

        # Buscar o último comentário inserido - CORRIGIDO PARA FIREBIRD
        # Firebird usa FIRST 1 em vez de LIMIT 1
        cur.execute("""
            SELECT FIRST 1 ID_COMENTARIOS 
            FROM COMENTARIOS 
            WHERE ID_USUARIOS_DOADOR = ? AND ID_ATUALIZACOES = ? 
            ORDER BY ID_COMENTARIOS DESC
        """, (id_doador, id_atualizacao))
        comentario = cur.fetchone()

        data_str = data_atual.strftime('%d/%m/%Y %H:%M')

        comentario_retorno = {
            'id': comentario[0] if comentario else None,
            'usuario_id': id_doador,
            'texto': texto,
            'data_criacao': data_str,
            'usuario_nome': usuario[0] if usuario else 'Usuário',
            'usuario_foto': f'{usuario[1]}.jpeg' if usuario else None
        }

        return jsonify({
            'message': 'Comentário adicionado com sucesso!',
            'comentario': comentario_retorno
        }), 201

    except Exception as e:
        con.rollback()
        print(f"ERRO ao comentar: {e}")
        return jsonify({'error': f'Erro ao comentar: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/deletar_comentario/<int:id_comentario>', methods=['DELETE', 'OPTIONS'])
def deletar_comentario(id_comentario):
    """Deleta um comentário (apenas o autor ou admin)"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        print(f"Tentando deletar comentário {id_comentario}")

        # Verificar autenticação
        token_data = decodificar_token()
        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado'}), 401

        id_usuario = token_data['id_usuarios']
        tipo_usuario = token_data['tipo']

        # Buscar o comentário
        cur.execute("""
            SELECT ID_COMENTARIOS, ID_USUARIOS_DOADOR FROM COMENTARIOS 
            WHERE ID_COMENTARIOS = ?
        """, (id_comentario,))
        comentario = cur.fetchone()

        if not comentario:
            return jsonify({'error': 'Comentário não encontrado'}), 404

        # Verificar permissão (apenas o autor ou admin pode deletar)
        if tipo_usuario != 0 and comentario[1] != id_usuario:
            return jsonify({'error': 'Sem permissão para deletar este comentário'}), 403

        # Deletar comentário
        cur.execute("DELETE FROM COMENTARIOS WHERE ID_COMENTARIOS = ?", (id_comentario,))
        con.commit()

        return jsonify({'message': 'Comentário deletado com sucesso!'}), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO ao deletar comentário: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()