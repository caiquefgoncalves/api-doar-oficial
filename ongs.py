# ongs.py
from flask import jsonify, request, render_template
from funcao import enviando_email, decodificar_token, validar_adm, gerar_qr_pix
from main import app
from db import conexao
import threading




# ============================================
# ROTAS PÚBLICAS
# ============================================

@app.route('/listar_ongs_publicas', methods=['GET'])
def listar_ongs_publicas():
    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT ID_USUARIOS, NOME, DESCRICAO_BREVE, CATEGORIA, DATA_CADASTRO
            FROM USUARIOS 
            WHERE TIPO = 2 AND APROVACAO = 1 AND ATIVO = 1
            ORDER BY NOME
        """)
        ongs = cur.fetchall()
        lista = []
        if ongs:
            for o in ongs:
                data_str = o[4].strftime('%Y-%m-%d %H:%M:%S') if o[4] else ''
                lista.append({
                    'id': o[0],
                    'nome': o[1],
                    'descricao_breve': str(o[2]) if o[2] else '',
                    'categoria': str(o[3]) if o[3] else '',
                    'data_cadastro': data_str,
                    'foto': f'{o[0]}.jpeg'
                })
        return jsonify({'ongs': lista}), 200
    except Exception as e:
        print(f"ERRO listar_ongs_publicas: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/ver_ong_publica/<int:id_ong>', methods=['GET'])
def ver_ong_publica(id_ong):
    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""SELECT ID_USUARIOS, NOME, DESCRICAO_BREVE, DESCRICAO_LONGA,
        CPF_CNPJ, CATEGORIA, LOCALIZACAO, COD_BANCO, NUM_AGENCIA, CHAVE_PIX
        FROM USUARIOS WHERE ID_USUARIOS = ? AND TIPO = 2 AND APROVACAO = 1""", (id_ong,))
        ong = cur.fetchone()

        if not ong:
            return jsonify({"error": "ONG não encontrada"}), 404

        cnpj = ong[4]
        cnpj_formatado = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

        # Inicializar variáveis com valores padrão
        qtd_projetos = 0
        qtd_atualizacoes = 0
        dic_atualizacoes = []
        projetos_lista = []

        # Contar seguidores
        cur.execute("SELECT COUNT(*) FROM SEGUINDO WHERE ID_USUARIOS_ONG = ?", (id_ong,))
        qtd_seguidores = cur.fetchone()[0]

        # Gerar QR Code PIX
        nome_qr = None
        chave_pix = None
        if ong[9]:  # CHAVE_PIX está na posição 9
            try:
                resultado = gerar_qr_pix(
                    chave_pix=ong[9],
                    nome=ong[1],
                    cidade=ong[6] if ong[6] else '',
                    id_ong=ong[0],  # ← CORRIGIDO
                    pasta_base=app.config['UPLOAD_FOLDER']
                )
                nome_qr = resultado[0]
                chave_pix = resultado[1]
            except Exception as e:
                print(f"Erro ao gerar QR Code: {e}")

        cur.execute("""SELECT ID_PROJETOS, TITULO, DESCRICAO, TIPO_AJUDA
        FROM PROJETOS WHERE ID_USUARIOS = ? AND STATUS = 'Ativo'""", (id_ong,))
        projetos = cur.fetchall()

        if projetos:
            qtd_projetos = len(projetos)
            projetos_lista = []
            for p in projetos:
                if p[3] == "Dinheiro":
                    tipo_ajuda = 0
                else:
                    tipo_ajuda = 1
                projetos_lista.append({
                'id': p[0], 'titulo': p[1], 'descricao': p[2], 'tipo_ajuda': p[3], 'tipo_ajuda_numero': tipo_ajuda})

            ids_projetos = [p[0] for p in projetos]

            for proj_id in ids_projetos:
                cur.execute("""SELECT ID_ATUALIZACOES, ID_PROJETOS, TITULO, TEXTO
                    FROM ATUALIZACOES WHERE ID_PROJETOS = ?""", (proj_id,))
                atualizacao = cur.fetchall()

                for a in atualizacao:
                    dic_atualizacoes.append({
                        'id': a[0],
                        'projetos': a[1],
                        'titulo': a[2],
                        'texto': a[3]
                    })

            qtd_atualizacoes = len(dic_atualizacoes)

        return jsonify({
            'ong': {
                'id': ong[0], 'nome': ong[1], 'descricao_breve': ong[2],
                'descricao_longa': ong[3], 'cpf_cnpj': cnpj_formatado, 'categoria': ong[5],
                'localizacao': ong[6], 'cod_banco': ong[7], 'num_agencia': ong[8],
                'foto': f'{ong[0]}.jpeg',
                'pix': nome_qr,
                'chave_pix': chave_pix,
                'qtd_seguidores': qtd_seguidores
            },
            'qtd_projetos': qtd_projetos,
            'projetos': projetos_lista,
            'qtd_atualizacoes': qtd_atualizacoes,
            'atualizacoes': dic_atualizacoes
        }), 200
    except Exception as e:
        print(f"ERRO ver_ong_publica: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()
        con.close()
        print(f"DEBUG - CHAVE_PIX: {ong[9]}")
        print(f"DEBUG - NOME: {ong[1]}")
        print(f"DEBUG - CIDADE: {ong[6]}")
        print(f"DEBUG - QR gerado: {nome_qr}")

@app.route('/buscar', methods=['GET'])
def buscar():
    termo = request.args.get('q', '')
    tipo = request.args.get('tipo', 'todos')
    con = conexao()
    cur = con.cursor()
    resultado = {'ongs': [], 'projetos': []}
    try:
        if tipo in ['todos', 'ongs']:
            if termo:
                cur.execute("""SELECT ID_USUARIOS, NOME, DESCRICAO_BREVE, CATEGORIA FROM USUARIOS 
                               WHERE TIPO = 2 AND APROVACAO = 1 AND ATIVO = 1 
                               AND (NOME LIKE ? OR DESCRICAO_BREVE LIKE ? OR CATEGORIA LIKE ?)
                               ORDER BY NOME""", (f'%{termo}%', f'%{termo}%', f'%{termo}%'))
            else:
                cur.execute("""SELECT ID_USUARIOS, NOME, DESCRICAO_BREVE, CATEGORIA FROM USUARIOS 
                               WHERE TIPO = 2 AND APROVACAO = 1 AND ATIVO = 1 ORDER BY NOME""")
            ongs = cur.fetchall()
            resultado['ongs'] = [{'id': o[0], 'nome': o[1], 'descricao_breve': str(o[2]) if o[2] else '', 'categoria': str(o[3]) if o[3] else '', 'foto': f'{o[0]}.jpeg'} for o in ongs] if ongs else []

        if tipo in ['todos', 'projetos']:
            if termo:
                cur.execute("""SELECT p.ID_PROJETOS, p.TITULO, p.DESCRICAO, p.STATUS, p.CATEGORIA, u.NOME
                               FROM PROJETOS p INNER JOIN USUARIOS u ON p.ID_USUARIOS = u.ID_USUARIOS
                               WHERE u.APROVACAO = 1 AND u.ATIVO = 1 
                               AND (p.TITULO LIKE ? OR p.DESCRICAO LIKE ? OR p.CATEGORIA LIKE ?)
                               ORDER BY p.ID_PROJETOS DESC""", (f'%{termo}%', f'%{termo}%', f'%{termo}%'))
            else:
                cur.execute("""SELECT p.ID_PROJETOS, p.TITULO, p.DESCRICAO, p.STATUS, p.CATEGORIA, u.NOME
                               FROM PROJETOS p INNER JOIN USUARIOS u ON p.ID_USUARIOS = u.ID_USUARIOS
                               WHERE u.APROVACAO = 1 AND u.ATIVO = 1 ORDER BY p.ID_PROJETOS DESC""")
            projetos = cur.fetchall()
            resultado['projetos'] = [{'id': p[0], 'titulo': p[1], 'descricao': str(p[2]) if p[2] else '', 'status': str(p[3]) if p[3] else '', 'categoria': str(p[4]) if p[4] else '', 'ong_nome': str(p[5]) if p[5] else '', 'foto': f'{p[0]}.jpeg'} for p in projetos] if projetos else []

        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTAS ADMINISTRATIVAS
# ============================================

@app.route('/admin/listar_ongs', methods=['GET'])
def listar_ongs():
    erro = validar_adm()
    if erro: return erro

    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL, CPF_CNPJ, TELEFONE,
                              DESCRICAO_BREVE, DESCRICAO_LONGA, APROVACAO, COD_BANCO,
                              NUM_AGENCIA, NUM_CONTA, TIPO_CONTA, CHAVE_PIX, CATEGORIA,
                              ATIVO, LOCALIZACAO, DATA_CADASTRO, EMAIL_CONFIRMACAO, MOTIVO_REPROVACAO
                       FROM USUARIOS WHERE TIPO = 2 ORDER BY DATA_CADASTRO DESC""")
        ongs = cur.fetchall()

        if not ongs:
            return jsonify({'message': 'Nenhuma ONG cadastrada', 'ongs': []}), 200

        lista_ongs = []
        for ong in ongs:
            status = 'Pendente' if ong[7] == 0 else 'Aprovada' if ong[7] == 1 else 'Reprovada' if ong[7] == 2 else 'Desconhecido'
            lista_ongs.append({
                'id': ong[0], 'nome': ong[1], 'email': ong[2], 'cpf_cnpj': ong[3],
                'telefone': ong[4], 'descricao_breve': ong[5], 'descricao_longa': ong[6],
                'status': status, 'codigo_aprovacao': ong[7], 'cod_banco': ong[8],
                'num_agencia': ong[9], 'num_conta': ong[10], 'tipo_conta': ong[11],
                'chave_pix': ong[12], 'categoria': ong[13], 'ativo': bool(ong[14]),
                'localizacao': ong[15],
                'data_cadastro': ong[16].strftime('%d/%m/%Y %H:%M:%S') if ong[16] else None,
                'email_confirmado': bool(ong[17]),
                'motivo_reprovacao': ong[18] if len(ong) > 18 and ong[18] else None
            })

        return jsonify({'message': 'ONGs listadas', 'total': len(lista_ongs), 'ongs': lista_ongs}), 200
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/admin/buscar_ong', methods=['GET'])
def buscar_ong():
    erro = validar_adm()
    if erro: return erro

    ong_id = request.args.get('id')
    if not ong_id:
        return jsonify({'error': 'Forneça um ID'}), 400

    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL, CPF_CNPJ, TELEFONE,
                              DESCRICAO_BREVE, DESCRICAO_LONGA, APROVACAO, COD_BANCO,
                              NUM_AGENCIA, NUM_CONTA, TIPO_CONTA, CHAVE_PIX, CATEGORIA,
                              ATIVO, LOCALIZACAO, DATA_CADASTRO, EMAIL_CONFIRMACAO, MOTIVO_REPROVACAO
                       FROM USUARIOS WHERE TIPO = 2 AND ID_USUARIOS = ?""", (ong_id,))
        ong = cur.fetchone()
        if not ong:
            return jsonify({'error': 'ONG não encontrada'}), 404

        status = 'Pendente' if ong[7] == 0 else 'Aprovada' if ong[7] == 1 else 'Reprovada' if ong[7] == 2 else 'Desconhecido'
        return jsonify({'ong': {
            'id': ong[0], 'nome': ong[1], 'email': ong[2], 'cpf_cnpj': ong[3],
            'telefone': ong[4], 'descricao_breve': ong[5], 'descricao_longa': ong[6],
            'status': status, 'codigo_aprovacao': ong[7], 'cod_banco': ong[8],
            'num_agencia': ong[9], 'num_conta': ong[10], 'tipo_conta': ong[11],
            'chave_pix': ong[12], 'categoria': ong[13], 'ativo': bool(ong[14]),
            'localizacao': ong[15],
            'data_cadastro': ong[16].strftime('%d/%m/%Y %H:%M:%S') if ong[16] else None,
            'email_confirmado': bool(ong[17]),
            'motivo_reprovacao': ong[18] if len(ong) > 18 and ong[18] else None
        }}), 200
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/admin/aprovar_ong/<int:id_usuarios>', methods=['PUT'])
def aprovar_ong(id_usuarios):
    erro = validar_adm()
    if erro: return erro

    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("SELECT ID_USUARIOS, NOME, EMAIL, APROVACAO FROM USUARIOS WHERE ID_USUARIOS = ? AND TIPO = 2", (id_usuarios,))
        ong = cur.fetchone()
        if not ong: return jsonify({'error': 'ONG não encontrada'}), 404
        if ong[3] == 1: return jsonify({'message': 'ONG já está aprovada'}), 200

        cur.execute("UPDATE USUARIOS SET APROVACAO = 1, MOTIVO_REPROVACAO = NULL WHERE ID_USUARIOS = ?", (id_usuarios,))
        con.commit()

        html = render_template('template_aprovacao.html', nome=ong[1], mensagem=f'Parabéns {ong[1]}! Sua ONG foi aprovada.')
        threading.Thread(target=enviando_email, args=(ong[2], 'ONG Aprovada - Doar +', html)).start()

        return jsonify({'message': f'ONG {ong[1]} aprovada!', 'id': id_usuarios}), 200
    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/admin/reprovar_ong/<int:id_usuarios>', methods=['PUT'])
def reprovar_ong(id_usuarios):
    erro = validar_adm()
    if erro: return erro

    motivo = request.json.get('motivo', 'Não especificado')
    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("SELECT ID_USUARIOS, NOME, EMAIL, APROVACAO FROM USUARIOS WHERE ID_USUARIOS = ? AND TIPO = 2", (id_usuarios,))
        ong = cur.fetchone()
        if not ong: return jsonify({'error': 'ONG não encontrada'}), 404
        if ong[3] == 2: return jsonify({'message': 'ONG já está reprovada'}), 200

        cur.execute("UPDATE USUARIOS SET APROVACAO = 2, MOTIVO_REPROVACAO = ? WHERE ID_USUARIOS = ?", (motivo, id_usuarios))
        con.commit()

        html = render_template('template_reprovacao.html', nome=ong[1], mensagem=f'Olá {ong[1]}, sua ONG não foi aprovada.', motivo=motivo)
        threading.Thread(target=enviando_email, args=(ong[2], 'Atualização ONG - Doar +', html)).start()

        return jsonify({'message': f'ONG {ong[1]} reprovada', 'motivo': motivo}), 200
    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/admin/bloquear_ong/<int:id_usuarios>', methods=['PUT'])
def bloquear_ong(id_usuarios):
    erro = validar_adm()
    if erro: return erro

    acao = request.json.get('acao', 'bloquear')
    motivo = request.json.get('motivo', '')

    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("SELECT ID_USUARIOS, NOME, EMAIL FROM USUARIOS WHERE ID_USUARIOS = ? AND TIPO = 2", (id_usuarios,))
        ong = cur.fetchone()
        if not ong: return jsonify({'error': 'ONG não encontrada'}), 404

        novo_status = 0 if acao == 'bloquear' else 1
        cur.execute("UPDATE USUARIOS SET ATIVO = ? WHERE ID_USUARIOS = ?", (novo_status, id_usuarios))
        con.commit()


        if acao == 'bloquear' and motivo:
            html = render_template('template_bloqueio.html', nome=ong[1], motivo=motivo)
            threading.Thread(target=enviando_email, args=(ong[2], 'Sua ONG foi bloqueada - Doar +', html)).start()

        return jsonify({'message': f'ONG {ong[1]} {"bloqueada" if acao == "bloquear" else "desbloqueada"}!'}), 200
    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/admin/deletar_ong/<int:id_usuarios>', methods=['DELETE'])
def deletar_ong(id_usuarios):
    erro = validar_adm()
    if erro: return erro

    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("SELECT ID_USUARIOS, NOME, ATIVO, APROVACAO FROM USUARIOS WHERE ID_USUARIOS = ? AND TIPO = 2",
                    (id_usuarios,))
        ong = cur.fetchone()
        if not ong: return jsonify({'error': 'ONG não encontrada'}), 404
        if ong[2] == 1 and ong[3] != 2:
            return jsonify({'error': 'Apenas ONGs bloqueadas ou reprovadas podem ser excluídas'}), 403

        # 1. Buscar projetos da ONG
        cur.execute("SELECT ID_PROJETOS FROM PROJETOS WHERE ID_USUARIOS = ?", (id_usuarios,))
        projetos = cur.fetchall()

        # 2. Excluir atualizações de cada projeto
        for projeto in projetos:
            cur.execute("DELETE FROM ATUALIZACOES WHERE ID_PROJETOS = ?", (projeto[0],))

        # 3. Excluir projetos da ONG
        cur.execute("DELETE FROM PROJETOS WHERE ID_USUARIOS = ?", (id_usuarios,))

        # 4. Excluir histórico e recuperação
        cur.execute("DELETE FROM HISTORICO_SENHA WHERE ID_USUARIOS = ?", (id_usuarios,))
        cur.execute("DELETE FROM RECUPERACAO_SENHA WHERE ID_USUARIOS = ?", (id_usuarios,))

        # 5. Excluir a ONG
        cur.execute("DELETE FROM USUARIOS WHERE ID_USUARIOS = ?", (id_usuarios,))

        con.commit()
        return jsonify({'message': f'ONG {ong[1]} excluída com sucesso!'}), 200
    except Exception as e:
        con.rollback()
        print(f"ERRO deletar_ong: {e}")
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/ong/editar_perfil/<int:id_usuarios>', methods=['PUT'])
def editar_perfil_ong(id_usuarios):
    con = conexao()
    cur = con.cursor()
    try:
        token_data = decodificar_token()
        if token_data == False:
            return jsonify({'error': 'Token necessário'}), 401
        if token_data['id_usuarios'] != id_usuarios:
            return jsonify({'error': 'Você só pode editar seu próprio perfil'}), 403
        if token_data['tipo'] != 2:
            return jsonify({'error': 'Apenas ONGs podem acessar esta rota'}), 403

        cur.execute("SELECT * FROM USUARIOS WHERE ID_USUARIOS = ? AND TIPO = 2", (id_usuarios,))
        ong_atual = cur.fetchone()
        if not ong_atual:
            return jsonify({'error': 'ONG não encontrada'}), 404

        nome = request.form.get('nome', ong_atual[1])
        email = request.form.get('email', ong_atual[2])
        cpf_cnpj = request.form.get('cpf_cnpj', ong_atual[4])
        telefone = request.form.get('telefone', ong_atual[5])
        descricao_breve = request.form.get('descricao_breve', ong_atual[6])
        descricao_longa = request.form.get('descricao_longa', ong_atual[7])
        cod_banco = request.form.get('cod_banco', ong_atual[9])
        num_agencia = request.form.get('num_agencia', ong_atual[10])
        num_conta = request.form.get('num_conta', ong_atual[11])
        tipo_conta = request.form.get('tipo_conta', ong_atual[12])
        chave_pix = request.form.get('chave_pix', ong_atual[13])
        categoria = request.form.get('categoria', ong_atual[14])
        localizacao = request.form.get('localizacao', ong_atual[16])
        senha = request.form.get('senha', None)
        confirmar_senha = request.form.get('confirmar_senha', None)

        from flask_bcrypt import generate_password_hash
        from funcao import senha_forte, senha_correspondente, senha_antiga

        nova_senha_hash = ong_atual[3]
        if senha:
            if not senha_correspondente(senha, confirmar_senha):
                return jsonify({'error': 'Senhas não correspondem'}), 400
            nova_senha_hash = generate_password_hash(senha).decode('utf-8')

        cur.execute("""UPDATE USUARIOS SET NOME=?, EMAIL=?, SENHA=?, CPF_CNPJ=?, TELEFONE=?,
                       DESCRICAO_BREVE=?, DESCRICAO_LONGA=?, COD_BANCO=?, NUM_AGENCIA=?,
                       NUM_CONTA=?, TIPO_CONTA=?, CHAVE_PIX=?, CATEGORIA=?, LOCALIZACAO=?
                       WHERE ID_USUARIOS=?""",
                    (nome, email, nova_senha_hash, cpf_cnpj, telefone, descricao_breve,
                     descricao_longa, cod_banco, num_agencia, num_conta, tipo_conta,
                     chave_pix, categoria, localizacao, id_usuarios))
        con.commit()
        return jsonify({'message': 'Perfil atualizado com sucesso!'}), 200
    except Exception as e:
        con.rollback()
        return jsonify({'error': f'Erro: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/buscar_ong_logada/<int:id_ong>', methods=['GET'])
def buscar_ong_logada(id_ong):
    """ONG logada busca seus próprios dados"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401

    # Só a própria ONG ou ADM pode ver
    if token_data['tipo'] != 0 and token_data['id_usuarios'] != id_ong:
        return jsonify({'error': 'Sem permissão'}), 403

    con = conexao()
    cur = con.cursor()
    try:
        cur.execute("""SELECT ID_USUARIOS, NOME, EMAIL, CPF_CNPJ, TELEFONE,
                              DESCRICAO_BREVE, DESCRICAO_LONGA, APROVACAO, COD_BANCO,
                              NUM_AGENCIA, NUM_CONTA, TIPO_CONTA, CHAVE_PIX, CATEGORIA,
                              ATIVO, LOCALIZACAO
                       FROM USUARIOS WHERE ID_USUARIOS = ? AND TIPO = 2""", (id_ong,))
        ong = cur.fetchone()
        if not ong:
            return jsonify({'error': 'ONG não encontrada'}), 404

        return jsonify({'ong': {
            'id': ong[0], 'nome': ong[1], 'email': ong[2], 'cpf_cnpj': ong[3],
            'telefone': ong[4], 'descricao_breve': ong[5], 'descricao_longa': ong[6],
            'codigo_aprovacao': ong[7], 'cod_banco': ong[8], 'num_agencia': ong[9],
            'num_conta': ong[10], 'tipo_conta': ong[11], 'chave_pix': ong[12],
            'categoria': ong[13], 'ativo': bool(ong[14]), 'localizacao': ong[15]
        }}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# ROTAS DE SEGUIR/DESSEGUIR ONGS
# ============================================

@app.route('/seguir/<int:id_ong>', methods=['POST', 'OPTIONS'])
def seguir_ong(id_ong):
    """Doador segue uma ONG"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        # Debug: Mostra os headers recebidos
        print("=" * 50)
        print("ROTA SEGUIR - Headers recebidos:")
        print(f"Authorization: {request.headers.get('Authorization')}")
        print(f"Cookies: {request.cookies}")
        print("=" * 50)

        # Verifica token
        token_data = decodificar_token()
        print(f"Token data: {token_data}")  # Debug

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado para seguir uma ONG'}), 401

        # Verifica se é doador (tipo 1)
        print(f"Tipo de usuário: {token_data.get('tipo')}")  # Debug
        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem seguir ONGs'}), 403

        id_doador = token_data['id_usuarios']
        print(f"ID do doador: {id_doador}")  # Debug

        # Verifica se a ONG existe e está aprovada e ativa
        cur.execute("""
            SELECT ID_USUARIOS, NOME FROM USUARIOS 
            WHERE ID_USUARIOS = ? AND TIPO = 2 AND APROVACAO = 1 AND ATIVO = 1
        """, (id_ong,))
        ong = cur.fetchone()
        print(f"ONG encontrada: {ong}")  # Debug

        if not ong:
            return jsonify({'error': 'ONG não encontrada ou não está disponível'}), 404

        # Verifica se já está seguindo (apenas verifica existência do registro)
        cur.execute("""
            SELECT ID_SEGUINDO FROM SEGUINDO 
            WHERE ID_USUARIOS_DOADOR = ? AND ID_USUARIOS_ONG = ?
        """, (id_doador, id_ong))
        seguindo = cur.fetchone()
        print(f"Já está seguindo? {seguindo}")  # Debug

        if seguindo:
            return jsonify({
                'message': 'Você já está seguindo esta ONG',
                'seguindo': True
            }), 200

        # Criar novo follow
        cur.execute("""
            INSERT INTO SEGUINDO (ID_USUARIOS_DOADOR, ID_USUARIOS_ONG)
            VALUES (?, ?)
        """, (id_doador, id_ong))
        con.commit()
        print("Novo follow criado com sucesso!")  # Debug

        return jsonify({
            'message': f'Você agora está seguindo {ong[1]}',
            'seguindo': True
        }), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO ao seguir ONG: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao seguir ONG: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/desseguir/<int:id_ong>', methods=['POST', 'OPTIONS'])
def desseguir_ong(id_ong):
    """Doador deixa de seguir uma ONG"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        # Debug: Mostra os headers recebidos
        print("=" * 50)
        print("ROTA DESSEGUIR - Headers recebidos:")
        print(f"Authorization: {request.headers.get('Authorization')}")
        print(f"Cookies: {request.cookies}")
        print("=" * 50)

        # Verifica token
        token_data = decodificar_token()
        print(f"Token data: {token_data}")  # Debug

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado'}), 401

        # Verifica se é doador
        print(f"Tipo de usuário: {token_data.get('tipo')}")  # Debug
        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem desseguir ONGs'}), 403

        id_doador = token_data['id_usuarios']
        print(f"ID do doador: {id_doador}")  # Debug

        # Verifica se está seguindo (apenas verifica existência)
        cur.execute("""
            SELECT ID_SEGUINDO FROM SEGUINDO 
            WHERE ID_USUARIOS_DOADOR = ? AND ID_USUARIOS_ONG = ?
        """, (id_doador, id_ong))
        seguindo = cur.fetchone()
        print(f"Registro encontrado para desseguir? {seguindo}")  # Debug

        if not seguindo:
            return jsonify({'error': 'Você não está seguindo esta ONG'}), 404

        # Deletar o registro de seguir (já que não tem campo status)
        cur.execute("""
            DELETE FROM SEGUINDO 
            WHERE ID_USUARIOS_DOADOR = ? AND ID_USUARIOS_ONG = ?
        """, (id_doador, id_ong))
        con.commit()
        print("Registro deletado com sucesso!")  # Debug

        return jsonify({
            'message': 'Você deixou de seguir esta ONG',
            'seguindo': False
        }), 200

    except Exception as e:
        con.rollback()
        print(f"ERRO ao desseguir ONG: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao desseguir ONG: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/verificar_seguindo/<int:id_ong>', methods=['GET', 'OPTIONS'])
def verificar_seguindo(id_ong):
    """Verifica se o doador está seguindo a ONG"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        # Debug
        print("=" * 50)
        print("ROTA VERIFICAR SEGUINDO:")
        print(f"ID ONG: {id_ong}")
        print(f"Authorization: {request.headers.get('Authorization')}")
        print("=" * 50)

        token_data = decodificar_token()
        print(f"Token data: {token_data}")  # Debug

        # Se não estiver logado, retorna não seguindo
        if token_data == False:
            return jsonify({
                'seguindo': False,
                'logado': False,
                'is_doador': False
            }), 200

        # Se não for doador, retorna não seguindo
        if token_data['tipo'] != 1:
            return jsonify({
                'seguindo': False,
                'logado': True,
                'is_doador': False
            }), 200

        id_doador = token_data['id_usuarios']
        print(f"Verificando follow: Doador {id_doador} -> ONG {id_ong}")  # Debug

        # Verifica se existe registro na tabela SEGUINDO
        cur.execute("""
            SELECT ID_SEGUINDO FROM SEGUINDO 
            WHERE ID_USUARIOS_DOADOR = ? AND ID_USUARIOS_ONG = ?
        """, (id_doador, id_ong))
        seguindo = cur.fetchone()
        print(f"Resultado: {'Seguindo' if seguindo else 'Não seguindo'}")  # Debug

        return jsonify({
            'seguindo': bool(seguindo),
            'logado': True,
            'is_doador': True
        }), 200

    except Exception as e:
        print(f"ERRO ao verificar seguindo: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao verificar: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/minhas_ongs_seguidas', methods=['GET', 'OPTIONS'])
def minhas_ongs_seguidas():
    """Lista todas as ONGs que o doador está seguindo"""
    if request.method == 'OPTIONS':
        return '', 200

    con = conexao()
    cur = con.cursor()

    try:
        # Debug
        print("=" * 50)
        print("ROTA MINHAS ONGS SEGUIDAS:")
        print(f"Authorization: {request.headers.get('Authorization')}")
        print("=" * 50)

        token_data = decodificar_token()
        print(f"Token data: {token_data}")  # Debug

        if token_data == False:
            return jsonify({'error': 'Você precisa estar logado'}), 401

        if token_data['tipo'] != 1:
            return jsonify({'error': 'Apenas doadores podem acessar'}), 403

        id_doador = token_data['id_usuarios']
        print(f"Buscando ONGs seguidas pelo doador: {id_doador}")  # Debug

        # Busca todas as ONGs que o doador segue
        cur.execute("""
            SELECT u.ID_USUARIOS, u.NOME, u.DESCRICAO_BREVE, u.CATEGORIA, u.LOCALIZACAO
            FROM SEGUINDO s
            INNER JOIN USUARIOS u ON s.ID_USUARIOS_ONG = u.ID_USUARIOS
            WHERE s.ID_USUARIOS_DOADOR = ? AND u.ATIVO = 1
            ORDER BY s.ID_SEGUINDO DESC
        """, (id_doador,))

        ongs = cur.fetchall()
        print(f"ONGs encontradas: {len(ongs) if ongs else 0}")  # Debug

        lista_ongs = []
        if ongs:
            for ong in ongs:
                lista_ongs.append({
                    'id': ong[0],
                    'nome': ong[1],
                    'descricao_breve': str(ong[2]) if ong[2] else '',
                    'categoria': str(ong[3]) if ong[3] else '',
                    'localizacao': str(ong[4]) if ong[4] else '',
                    'foto': f'{ong[0]}.jpeg'
                })

        return jsonify({
            'ongs': lista_ongs,
            'total': len(lista_ongs)
        }), 200

    except Exception as e:
        print(f"ERRO ao listar ONGs seguidas: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao listar ONGs seguidas: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/contador_seguidores/<int:id_ong>', methods=['GET'])
def contador_seguidores(id_ong):
    """Retorna o número de seguidores de uma ONG"""
    con = conexao()
    cur = con.cursor()

    try:
        # Debug
        print(f"Contando seguidores da ONG {id_ong}")  # Debug

        # Conta todos os registros na tabela SEGUINDO para esta ONG
        cur.execute("""
            SELECT COUNT(*) FROM SEGUINDO 
            WHERE ID_USUARIOS_ONG = ?
        """, (id_ong,))
        count = cur.fetchone()[0]
        print(f"Total de seguidores: {count}")  # Debug

        return jsonify({
            'seguidores': count,
            'ong_id': id_ong
        }), 200

    except Exception as e:
        print(f"ERRO ao contar seguidores: {str(e)}")  # Debug
        return jsonify({'error': f'Erro ao contar seguidores: {str(e)}'}), 500
    finally:
        cur.close()
        con.close()


@app.route('/ong/doadores/<int:id_ong>', methods=['GET'])
def doadores_ong(id_ong):
    """Retorna os doadores que fizeram pelo menos uma doação para a ONG"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem acessar'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        print(f"DEBUG - Buscando doadores da ONG {id_ong}")

        # Buscar o último valor doado por cada doador
        cur.execute("""
            SELECT 
                u.ID_USUARIOS, 
                u.NOME, 
                MAX(d.DATA_DOACAO) as ULTIMA_DOACAO,
                (SELECT FIRST 1 d2.VALOR 
                 FROM DOACOES d2 
                 INNER JOIN PROJETOS p2 ON d2.ID_PROJETOS = p2.ID_PROJETOS
                 WHERE d2.ID_USUARIOS = u.ID_USUARIOS AND p2.ID_USUARIOS = ?
                 ORDER BY d2.DATA_DOACAO DESC) as ULTIMO_VALOR
            FROM DOACOES d
            INNER JOIN USUARIOS u ON d.ID_USUARIOS = u.ID_USUARIOS
            INNER JOIN PROJETOS p ON d.ID_PROJETOS = p.ID_PROJETOS
            WHERE p.ID_USUARIOS = ?
            GROUP BY u.ID_USUARIOS, u.NOME
            ORDER BY ULTIMA_DOACAO DESC
        """, (id_ong, id_ong))

        doadores = cur.fetchall()
        print(f"DEBUG - Doadores encontrados: {len(doadores) if doadores else 0}")

        lista = []
        for d in doadores:
            data_str = ''
            if d[2]:
                try:
                    data_str = d[2].strftime('%d/%m/%Y')
                except:
                    data_str = str(d[2])
            lista.append({
                'id': d[0],
                'nome': d[1],
                'ultima_doacao': data_str,
                'ultimo_valor': f'R$ {float(d[3] or 0):.2f}'.replace('.', ','),
                'foto': f'{d[0]}.jpeg'
            })

        return jsonify({'doadores': lista}), 200

    except Exception as e:
        print(f"ERRO doadores_ong: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()