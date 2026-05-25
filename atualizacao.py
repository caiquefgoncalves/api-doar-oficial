# atualizacao.py
from flask import jsonify, request
from main import app
from db import conexao
from funcao import decodificar_token
import os
from datetime import datetime
import random


# ============================================
# ROTA: Feed de atualizações (público)
# ============================================
@app.route('/feed_atualizacoes', methods=['GET'])
def feed_atualizacoes():
    filtro = request.args.get('filtro', 'recentes')

    pagina = int(request.args.get('pagina', 0))
    limite = int(request.args.get('limite', 4))
    atualizacoes_puladas = pagina * limite

    con = conexao()
    cur = con.cursor()

    try:
        ordem = 'ASC' if filtro == 'antigos' else 'DESC'

        # Buscar atualizações
        cur.execute(f"""
            SELECT FIRST {limite} SKIP {atualizacoes_puladas}
            a.ID_ATUALIZACOES, a.ID_PROJETOS, a.TITULO,
            a.TEXTO, a.DATA_CRIACAO, p.ID_USUARIOS, p.TITULO AS TITULO_PROJETO,
            u.NOME,
            (SELECT COUNT(*) FROM CURTIDAS c WHERE c.ID_ATUALIZACOES = a.ID_ATUALIZACOES) AS QTD_CURTIDAS,
            (SELECT COUNT(*) FROM COMENTARIOS co WHERE co.ID_ATUALIZACOES = a.ID_ATUALIZACOES) AS QTD_COMENTARIOS
            FROM ATUALIZACOES a
            INNER JOIN PROJETOS p ON p.ID_PROJETOS = a.ID_PROJETOS
            INNER JOIN USUARIOS u ON u.ID_USUARIOS = p.ID_USUARIOS
            WHERE u.APROVACAO = 1 AND u.ATIVO = 1
            ORDER BY a.DATA_CRIACAO {ordem}
        """)

        dados = cur.fetchall()

        lista = []
        if dados:
            for a in dados:
                data_str = ''
                if a[4]:
                    try:
                        data_str = a[4].strftime('%d/%m/%Y %H:%M')
                    except:
                        data_str = str(a[4])
                lista.append({
                    'id': a[0],
                    'projeto_id': a[1],
                    'titulo': str(a[2]) if a[2] else '',
                    'texto': str(a[3]) if a[3] else '',
                    'data': data_str,
                    'ong_id': a[5] if a[5] else 0,
                    'projeto_titulo': str(a[6]) if a[6] else '',
                    'ong_nome': str(a[7]) if a[7] else 'ONG',
                    'ong_foto': f'{a[5]}.jpeg',
                    'foto': f'{a[0]}.jpeg',
                    'qtd_curtidas': a[8] if a[8] else 0,
                    'qtd_comentarios': a[9] if a[9] else 0
                })

        # Buscar ONGs aleatórias
        cur.execute("""
            SELECT FIRST 3 ID_USUARIOS, NOME
            FROM USUARIOS
            WHERE TIPO = 2 AND APROVACAO = 1 AND ATIVO = 1
            ORDER BY RAND()
        """)
        ongs_aleatorias = cur.fetchall()

        ongs = []
        for ong in ongs_aleatorias:
            ongs.append({
                "id": ong[0],
                "nome": ong[1],
                "foto": f'{ong[0]}.jpeg'
            })

        return jsonify({
            'atualizacoes': lista,
            'ongs': ongs,
            'total_atualizacoes': len(lista)
        }), 200

    except Exception as e:
        print(f"ERRO feed_atualizacoes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Listar atualizações da ONG logada
# ============================================
@app.route('/listar_atualizacoes', methods=['GET'])
def listar_atualizacoes_ong():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    id_usuarios = token_data['id_usuarios']
    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT a.ID_ATUALIZACOES, a.ID_PROJETOS, a.TITULO, a.TEXTO, a.DATA_CRIACAO
            FROM ATUALIZACOES a
            INNER JOIN PROJETOS p ON a.ID_PROJETOS = p.ID_PROJETOS
            WHERE p.ID_USUARIOS = ?
            ORDER BY a.DATA_CRIACAO DESC
        """, (id_usuarios,))

        atualizacoes = cur.fetchall()

        lista_atualizacoes = []
        for a in atualizacoes:
            data_str = ''
            if a[4]:
                try:
                    data_str = a[4].strftime('%d/%m/%Y %H:%M')
                except:
                    data_str = str(a[4])

            lista_atualizacoes.append({
                'id': a[0],
                'projeto_id': a[1],
                'titulo': str(a[2]) if a[2] else '',
                'texto': str(a[3]) if a[3] else '',
                'data': data_str,
                'foto': f'{a[0]}.jpeg'
            })

        return jsonify({'atualizacoes': lista_atualizacoes}), 200
    except Exception as e:
        print(f"ERRO listar_atualizacoes: {e}")
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Criar atualização
# ============================================
@app.route('/criar_atualizacao', methods=['POST'])
def criar_atualizacao():
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem criar atualizações'}), 403

    titulo = request.form.get('titulo', '')
    texto = request.form.get('texto', '')
    projeto_id = request.form.get('projeto_id', '')
    foto_atualizacao = request.files.get('foto')

    if not titulo.strip():
        return jsonify({"error": "Título é obrigatório"}), 400
    if not projeto_id:
        return jsonify({"error": "Projeto é obrigatório"}), 400

    con = conexao()
    cur = con.cursor()

    try:
        # Verifica se o projeto existe e pertence à ONG
        cur.execute("SELECT ID_USUARIOS FROM PROJETOS WHERE ID_PROJETOS = ?", (projeto_id,))
        projeto = cur.fetchone()
        if not projeto:
            return jsonify({"error": "Projeto não encontrado"}), 404

        if token_data['id_usuarios'] != projeto[0] and token_data['tipo'] != 0:
            return jsonify({'error': 'Sem permissão para este projeto'}), 403

        data_atual = datetime.now()

        # Gera o próximo ID manualmente
        cur.execute("SELECT GEN_ID(GEN_ATUALIZACOES, 1) FROM RDB$DATABASE")
        next_id = cur.fetchone()[0]

        # Insere com o ID gerado
        cur.execute("""INSERT INTO ATUALIZACOES (ID_ATUALIZACOES, ID_PROJETOS, TITULO, TEXTO, DATA_CRIACAO)
                       VALUES (?, ?, ?, ?, ?)""",
                    (next_id, projeto_id, titulo, texto, data_atual))

        con.commit()
        id_atualizacoes = next_id

        # Salva foto se enviada
        if foto_atualizacao:
            try:
                nome_imagem = f'{id_atualizacoes}.jpeg'
                caminho_destino = os.path.join(app.config['UPLOAD_FOLDER'], 'Atualizacoes')
                os.makedirs(caminho_destino, exist_ok=True)
                foto_atualizacao.save(os.path.join(caminho_destino, nome_imagem))
            except Exception as e:
                print(f"Erro ao salvar foto: {e}")

        return jsonify({'message': 'Atualização criada com sucesso!', 'id': id_atualizacoes}), 201
    except Exception as e:
        print(f"ERRO criar_atualizacao: {e}")
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Buscar atualização por ID
# ============================================
@app.route('/buscar_atualizacao/<int:id_atualizacoes>', methods=['GET'])
def buscar_atualizacao(id_atualizacoes):
    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""SELECT ID_ATUALIZACOES, ID_PROJETOS, TITULO, TEXTO, DATA_CRIACAO
                       FROM ATUALIZACOES WHERE ID_ATUALIZACOES = ?""", (id_atualizacoes,))
        a = cur.fetchone()

        if not a:
            return jsonify({"error": "Atualização não encontrada"}), 404

        data_str = ''
        if a[4]:
            try:
                data_str = a[4].strftime('%d/%m/%Y %H:%M')
            except:
                data_str = str(a[4])

        return jsonify({'atualizacao': {
            'id': a[0],
            'projeto_id': a[1],
            'titulo': str(a[2]) if a[2] else '',
            'texto': str(a[3]) if a[3] else '',
            'data': data_str
        }}), 200
    except Exception as e:
        print(f"ERRO buscar_atualizacao: {e}")
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Editar atualização
# ============================================
@app.route('/editar_atualizacao/<int:id_atualizacoes>', methods=['PUT'])
def editar_atualizacao(id_atualizacoes):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        # Verifica se a atualização existe
        cur.execute("SELECT ID_PROJETOS FROM ATUALIZACOES WHERE ID_ATUALIZACOES = ?", (id_atualizacoes,))
        atualizacao = cur.fetchone()
        if not atualizacao:
            return jsonify({"error": "Atualização não encontrada"}), 404

        # Verifica se o projeto pertence à ONG
        cur.execute("SELECT ID_USUARIOS FROM PROJETOS WHERE ID_PROJETOS = ?", (atualizacao[0],))
        projeto = cur.fetchone()

        if token_data['tipo'] != 0 and token_data['id_usuarios'] != projeto[0]:
            return jsonify({'error': 'Sem permissão'}), 403

        titulo = request.form.get('titulo', '')
        texto = request.form.get('texto', '')
        projeto_id = request.form.get('projeto_id', '')
        foto_atualizacao = request.files.get('foto')

        cur.execute("""UPDATE ATUALIZACOES SET ID_PROJETOS = ?, TITULO = ?, TEXTO = ?, DATA_CRIACAO = ?
                       WHERE ID_ATUALIZACOES = ?""",
                    (projeto_id, titulo, texto, datetime.now(), id_atualizacoes))
        con.commit()

        # Salva foto se enviada
        if foto_atualizacao:
            try:
                nome_imagem = f'{id_atualizacoes}.jpeg'
                caminho_destino = os.path.join(app.config['UPLOAD_FOLDER'], 'Atualizacoes')
                os.makedirs(caminho_destino, exist_ok=True)
                foto_atualizacao.save(os.path.join(caminho_destino, nome_imagem))
            except Exception as e:
                print(f"Erro ao salvar foto: {e}")

        return jsonify({'message': 'Atualização editada com sucesso!'}), 200
    except Exception as e:
        print(f"ERRO editar_atualizacao: {e}")
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTA: Deletar atualização
# ============================================
@app.route('/deletar_atualizacao/<int:id_atualizacoes>', methods=['DELETE'])
def deletar_atualizacao(id_atualizacoes):
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    con = conexao()
    cur = con.cursor()

    try:
        # Verifica se a atualização existe
        cur.execute("SELECT ID_PROJETOS FROM ATUALIZACOES WHERE ID_ATUALIZACOES = ?", (id_atualizacoes,))
        atualizacao = cur.fetchone()
        if not atualizacao:
            return jsonify({"error": "Atualização não encontrada"}), 404

        # Verifica se o projeto pertence à ONG
        cur.execute("SELECT ID_USUARIOS FROM PROJETOS WHERE ID_PROJETOS = ?", (atualizacao[0],))
        projeto = cur.fetchone()

        if token_data['tipo'] != 0 and token_data['id_usuarios'] != projeto[0]:
            return jsonify({'error': 'Sem permissão'}), 403

        cur.execute("DELETE FROM ATUALIZACOES WHERE ID_ATUALIZACOES = ?", (id_atualizacoes,))
        con.commit()

        return jsonify({'message': 'Atualização excluída com sucesso!'}), 200
    except Exception as e:
        print(f"ERRO deletar_atualizacao: {e}")
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/feed_favoritas', methods=['GET'])
def feed_favoritas():
    """Feed de postagens das ONGs que o doador segue"""

    # Verificar autenticação
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Login necessário'}), 401

    # Apenas doadores
    if token_data['tipo'] != 1:
        return jsonify({'error': 'Apenas doadores podem acessar'}), 403

    id_doador = token_data['id_usuarios']

    # Parâmetros de paginação e filtro
    filtro = request.args.get('filtro', 'recentes')
    pagina = int(request.args.get('pagina', 0))
    limite = int(request.args.get('limite', 4))

    con = conexao()
    cur = con.cursor()

    try:
        print(f"DEBUG - Feed favoritas - Doador ID: {id_doador}")

        # Verificar se o doador segue alguma ONG
        cur.execute("""
            SELECT ID_USUARIOS_ONG FROM SEGUINDO 
            WHERE ID_USUARIOS_DOADOR = ?
        """, (id_doador,))
        ongs_seguidas = [row[0] for row in cur.fetchall()]
        print(f"DEBUG - ONGs seguidas: {ongs_seguidas}")

        if not ongs_seguidas:
            return jsonify({'atualizacoes': [], 'total': 0}), 200

        # Definir ordem
        if filtro == 'antigos':
            ordem = 'ASC'
        else:
            ordem = 'DESC'

        # Criar placeholders para os IDs das ONGs
        placeholders = ','.join(['?'] * len(ongs_seguidas))

        # Buscar atualizações dessas ONGs (sem FIRST/SKIP para evitar erro)
        cur.execute(f"""
            SELECT 
                a.ID_ATUALIZACOES,
                a.ID_PROJETOS,
                a.TITULO,
                a.TEXTO,
                a.DATA_CRIACAO,
                u.ID_USUARIOS,
                u.NOME
            FROM ATUALIZACOES a
            INNER JOIN PROJETOS p ON a.ID_PROJETOS = p.ID_PROJETOS
            INNER JOIN USUARIOS u ON p.ID_USUARIOS = u.ID_USUARIOS
            WHERE p.ID_USUARIOS IN ({placeholders})
                AND u.ATIVO = 1 
                AND u.APROVACAO = 1
            ORDER BY a.DATA_CRIACAO {ordem}
        """, ongs_seguidas)

        todas_atualizacoes = cur.fetchall()
        print(f"DEBUG - Total de atualizações encontradas: {len(todas_atualizacoes) if todas_atualizacoes else 0}")

        # Aplicar paginação manualmente
        inicio = pagina * limite
        fim = inicio + limite
        atualizacoes_paginadas = todas_atualizacoes[inicio:fim] if todas_atualizacoes else []

        lista = []
        for att in atualizacoes_paginadas:
            data_str = ''
            if att[4]:
                try:
                    data_str = att[4].strftime('%d/%m/%Y %H:%M')
                except:
                    data_str = str(att[4])

            id_att = att[0]
            id_ong = att[5]

            # Buscar contagens de curtidas
            cur.execute("SELECT COUNT(*) FROM CURTIDAS WHERE ID_ATUALIZACOES = ?", (id_att,))
            qtd_curtidas = cur.fetchone()[0] or 0

            # Buscar contagens de comentários
            cur.execute("SELECT COUNT(*) FROM COMENTARIOS WHERE ID_ATUALIZACOES = ?", (id_att,))
            qtd_comentarios = cur.fetchone()[0] or 0

            lista.append({
                'id': id_att,
                'projeto_id': att[1],
                'titulo': str(att[2]) if att[2] else '',
                'texto': str(att[3]) if att[3] else '',
                'data': data_str,
                'foto': f'{id_att}.jpeg',
                'ong_id': id_ong,
                'ong_nome': str(att[6]) if att[6] else 'ONG',
                'ong_foto': f'{id_ong}.jpeg' if id_ong else 'ong-icon.png',
                'qtd_curtidas': qtd_curtidas,
                'qtd_comentarios': qtd_comentarios
            })

        print(f"DEBUG - Retornando {len(lista)} atualizações")

        return jsonify({
            'atualizacoes': lista,
            'total': len(todas_atualizacoes) if todas_atualizacoes else 0
        }), 200

    except Exception as e:
        print(f"ERRO feed_favoritas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()

@app.route('/curtir/<int:id_atualizacoes>', methods=['POST', 'OPTIONS'])
def curtir(id_atualizacoes):
    """Doador segue uma ONG"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        # Verifica token
        token_data = decodificar_token()

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado para seguir uma ONG'}), 401

        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem curtir atualizações'}), 403

        id_doador = token_data['id_usuarios']

        cur.execute("""
            SELECT ID_ATUALIZACOES FROM ATUALIZACOES 
            WHERE ID_ATUALIZACOES = ?
        """, (id_atualizacoes,))
        atualizacao = cur.fetchone()

        if not atualizacao:
            return jsonify({'error': 'Atualização não encontrada ou não está disponível'}), 404

        # Verifica se já está curtido (apenas verifica existência do registro)
        cur.execute("""
            SELECT ID_CURTIDAS FROM CURTIDAS 
            WHERE ID_USUARIOS_DOADOR = ? AND ID_ATUALIZACOES = ?
        """, (id_doador, id_atualizacoes))
        curtida = cur.fetchone()

        if curtida:
            return jsonify({
                'message': 'Você já está seguindo esta ONG',
                'seguindo': True
            }), 200

        # Criar nova curtida
        cur.execute("""
            INSERT INTO CURTIDAS (ID_USUARIOS_DOADOR, ID_ATUALIZACOES)
            VALUES (?, ?)
        """, (id_doador, id_atualizacoes))
        con.commit()

        return jsonify({
            'message': f'Você curtiu essa atualização!',
            'curtido': True
        }), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO ao curtir ONG: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao seguir ONG: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/descurtir/<int:id_atualizacoes>', methods=['POST', 'OPTIONS'])
def descurtir(id_atualizacoes):
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:

        # Verifica token
        token_data = decodificar_token()

        print('entrei')

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado'}), 401

        # Verifica se é doador
        print(f"Tipo de usuário: {token_data.get('tipo')}")  # Debug
        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem fazer isso'}), 403

        print('sou doador')
        id_doador = token_data['id_usuarios']

        # Verifica se está curtido (apenas verifica existência)
        cur.execute("""
            SELECT ID_CURTIDAS FROM CURTIDAS
            WHERE ID_USUARIOS_DOADOR = ? AND ID_ATUALIZACOES = ?
        """, (id_doador, id_atualizacoes))
        curtida = cur.fetchone()

        if not curtida:
            return jsonify({'error': 'Você não curtiu essa atualização'}), 404

        print('tem mesmo')
        # Deletar o registro de curtida (já que não tem campo status)
        cur.execute("""
            DELETE FROM CURTIDAS
            WHERE ID_USUARIOS_DOADOR = ? AND ID_ATUALIZACOES = ?
        """, (id_doador, id_atualizacoes))
        con.commit()


        return jsonify({
            'message': 'Você descurtiu essa atualização',
            'curtido': False
        }), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO ao descurtir ONG: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao desseguir ONG: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()

@app.route('/verificar_curtida/<int:id_atualizacoes>', methods=['GET', 'OPTIONS'])
def verificar_curtida(id_atualizacoes):
    """Verifica se o doador está seguindo a ONG"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:

        token_data = decodificar_token()

        # Se não estiver logado, retorna não curtido
        if token_data == False:
            return jsonify({
                'curtido': False,
                'logado': False,
                'is_doador': False
            }), 200


        # Se não for doador, retorna não curtido
        if token_data['tipo'] != 1:
            return jsonify({
                'curtido': False,
                'logado': True,
                'is_doador': False
            }), 200


        id_doador = token_data['id_usuarios']

        # Verifica se existe registro na tabela CURTIDAS
        cur.execute("""
            SELECT ID_CURTIDAS FROM CURTIDAS 
            WHERE ID_USUARIOS_DOADOR = ? AND ID_ATUALIZACOES = ?
        """, (id_doador, id_atualizacoes))
        curtida = cur.fetchone()

        if curtida:
            return jsonify({
                'curtido': True,
                'logado': True,
                'is_doador': True
            }), 200
        else:
            return jsonify({
                'curtido': False,
                'logado': True,
                'is_doador': True
            }), 200


    except Exception as e:
        print(f"ERRO ao verificar seguindo: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao verificar: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/ongs_recomendacoes', methods=['GET'])
def ongs_recomendacoes():
    con = conexao()
    cur = con.cursor()

    try:
        # 💡 TRUQUE INTELIGENTE:
        # Se o front-end enviou o token puro no Authorization (sem Bearer),
        # nós interceptamos e ajustamos aqui dentro da rota, antes de chamar a sua função.
        auth_header = request.headers.get('Authorization')
        if auth_header and not auth_header.startswith('Bearer '):
            # Injeta o 'Bearer ' temporariamente na requisição para o seu decodificar_token() aceitar!
            request.environ['HTTP_AUTHORIZATION'] = f"Bearer {auth_header.strip()}"

        # 1. Agora o seu decodificar_token() vai funcionar perfeitamente!
        token_data = decodificar_token()

        # Se o usuário estiver logado e for um Doador (tipo = 1)
        if token_data and token_data != False and isinstance(token_data, dict) and token_data.get('tipo') == 1:
            id_usuario = token_data['id_usuarios']

            # 2. Busca 3 ONGs aleatórias onde NÃO exista registro na sua tabela SEGUINDO para este doador
            cur.execute("""
                SELECT FIRST 3 u.ID_USUARIOS, u.NOME
                FROM USUARIOS u
                WHERE u.TIPO = 2 AND u.APROVACAO = 1 AND u.ATIVO = 1
                AND NOT EXISTS (
                    SELECT 1 FROM SEGUINDO s 
                    WHERE s.ID_USUARIOS_ONG = u.ID_USUARIOS 
                    AND s.ID_USUARIOS_DOADOR = ?
                )
                ORDER BY RAND()
            """, (id_usuario,))

        else:
            # Se não estiver logado ou não for doador, busca 3 ONGs aleatórias gerais
            cur.execute("""
                SELECT FIRST 3 ID_USUARIOS, NOME
                FROM USUARIOS
                WHERE TIPO = 2 AND APROVACAO = 1 AND ATIVO = 1
                ORDER BY RAND()
            """)

        ongs_aleatorias = cur.fetchall()

        ongs = []
        for ong in ongs_aleatorias:
            ongs.append({
                "id": ong[0],
                "nome": ong[1],
                "foto": f'{ong[0]}.jpeg'
            })

        return jsonify({'ongs': ongs}), 200

    except Exception as e:
        print(f"ERRO ongs_recomendacoes: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()