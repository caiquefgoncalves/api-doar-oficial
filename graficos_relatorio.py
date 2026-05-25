
from flask import jsonify, request, Response, send_file
from main import app
from db import conexao
from funcao import decodificar_token, formatar_cpf, footer, header, resumo_3_colunas, ranking_lista, formatar_cnpj
import pygal
from pygal.style import Style
from fpdf import FPDF
import os



@app.route('/minhas_doacoes', methods=['GET'])
def minhas_doacoes():
    """Retorna as doações e voluntariados do doador logado"""
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
            SELECT d.VALOR, d.DATA_DOACAO, p.TITULO, u.NOME as ONG_NOME, u.ID_USUARIOS as ONG_ID, 'Monetário' as TIPO
            FROM DOACOES d
            INNER JOIN PROJETOS p ON d.ID_PROJETOS = p.ID_PROJETOS
            INNER JOIN USUARIOS u ON p.ID_USUARIOS = u.ID_USUARIOS
            WHERE d.ID_USUARIOS = ?
            ORDER BY d.DATA_DOACAO DESC
        """, (id_doador,))
        doacoes = cur.fetchall()

        cur.execute("""
            SELECT v.ID_VOLUNTARIADO, p.TITULO, u.NOME as ONG_NOME, u.ID_USUARIOS as ONG_ID, 'Voluntariado' as TIPO
            FROM VOLUNTARIADO v
            INNER JOIN PROJETOS p ON v.ID_PROJETOS = p.ID_PROJETOS
            INNER JOIN USUARIOS u ON p.ID_USUARIOS = u.ID_USUARIOS
            WHERE v.ID_USUARIOS = ?
            ORDER BY v.ID_VOLUNTARIADO DESC
        """, (id_doador,))
        voluntariados = cur.fetchall()

        atividades = []

        for d in doacoes:
            data_str = ''
            if d[1]:
                try:
                    data_str = d[1].strftime('%d/%m/%Y')
                except:
                    data_str = str(d[1])
            atividades.append({
                'tipo': 'Monetário',
                'valor': f'R$ {d[0]:.2f}'.replace('.', ','),
                'projeto': d[2],
                'ong': d[3],
                'ong_foto': f'{d[4]}.jpeg',
                'data': data_str
            })

        for v in voluntariados:
            atividades.append({
                'tipo': 'Voluntariado',
                'valor': 'Mensagem enviada',
                'projeto': v[1],
                'ong': v[2],
                'ong_foto': f'{v[3]}.jpeg',
                'data': ''
            })

        return jsonify({'atividades': atividades, 'total': len(atividades)}), 200

    except Exception as e:
        print(f"ERRO minhas_doacoes: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/frequencia_doacoes', methods=['GET'])
def frequencia_doacoes():
    """Retorna dados para o gráfico com todos os 12 meses"""
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
            SELECT 
                EXTRACT(MONTH FROM d.DATA_DOACAO) as MES,
                COUNT(*) as QTD
            FROM DOACOES d
            WHERE d.ID_USUARIOS = ? 
            AND EXTRACT(YEAR FROM d.DATA_DOACAO) = 2026
            GROUP BY EXTRACT(MONTH FROM d.DATA_DOACAO)
            ORDER BY MES
        """, (id_doador,))
        doacoes_mes = cur.fetchall()

        meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        dados_meses = {mes: 0 for mes in meses}

        for d in doacoes_mes:
            if d[0] and 1 <= int(d[0]) <= 12:
                dados_meses[meses[int(d[0]) - 1]] = int(d[1])

        dados = [{'mes': mes, 'qtd': qtd} for mes, qtd in dados_meses.items()]

        return jsonify({'dados': dados}), 200

    except Exception as e:
        print(f"ERRO frequencia_doacoes: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/arrecadacao_mensal_ong', methods=['GET'])
def arrecadacao_mensal_ong():
    """Retorna dados de arrecadação mensal para a ONG logada"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem acessar'}), 403

    id_ong = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        # arrecadacao_mensal_ong (ONG)
        cur.execute("""
            SELECT 
                EXTRACT(MONTH FROM d.DATA_DOACAO) as MES,
                SUM(d.VALOR) as TOTAL
            FROM DOACOES d
            INNER JOIN PROJETOS p ON d.ID_PROJETOS = p.ID_PROJETOS
            WHERE p.ID_USUARIOS = ?
            AND EXTRACT(YEAR FROM d.DATA_DOACAO) = 2026
            GROUP BY EXTRACT(MONTH FROM d.DATA_DOACAO)
            ORDER BY MES
        """, (id_ong,))
        doacoes_mes = cur.fetchall()

        meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        dados_meses = {mes: 0 for mes in meses}

        for d in doacoes_mes:
            if d[0] and 1 <= int(d[0]) <= 12:
                dados_meses[meses[int(d[0]) - 1]] = float(d[1])

        dados = [{'mes': mes, 'valor': valor} for mes, valor in dados_meses.items()]

        return jsonify({'dados': dados}), 200

    except Exception as e:
        print(f"ERRO arrecadacao_mensal_ong: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/admin/arrecadacao_global', methods=['GET'])
def arrecadacao_global():
    """Retorna dados de arrecadação global (todas as ONGs) por mês"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 0:
        return jsonify({'error': 'Apenas administradores podem acessar'}), 403

    con = conexao()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT 
                EXTRACT(MONTH FROM d.DATA_DOACAO) as MES,
                SUM(d.VALOR) as TOTAL
            FROM DOACOES d
            WHERE EXTRACT(YEAR FROM d.DATA_DOACAO) = 2026
            GROUP BY EXTRACT(MONTH FROM d.DATA_DOACAO)
            ORDER BY MES
        """)
        doacoes_mes = cur.fetchall()

        meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        dados_meses = {mes: 0 for mes in meses}

        for d in doacoes_mes:
            if d[0] and 1 <= int(d[0]) <= 12:
                dados_meses[meses[int(d[0]) - 1]] = float(d[1])

        dados = [{'mes': mes, 'valor': valor} for mes, valor in dados_meses.items()]

        return jsonify({'dados': dados}), 200

    except Exception as e:
        print(f"ERRO arrecadacao_global: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


@app.route('/admin/relatorio_doadores', methods=['GET'])
def relatorio_doadores():
    con = conexao()
    cur = con.cursor()

    try:
        # Lista de doadores em ordem crescente por ID
        cur.execute("""
            SELECT ID_USUARIOS, NOME, CPF_CNPJ, EMAIL
            FROM USUARIOS
            WHERE TIPO = 1
            ORDER BY ID_USUARIOS ASC
        """)
        usuarios = cur.fetchall()

        if not usuarios:
            return jsonify({'error': 'Nenhum doador encontrado'}), 404

        total_doadores = len(usuarios)

        cur.execute("SELECT COALESCE(SUM(VALOR), 0), COUNT(*) FROM DOACOES")
        total_valor, total_doacoes = cur.fetchone()

        # Top 5 maiores doadores (por valor)
        cur.execute("""
            SELECT U.NOME, SUM(D.VALOR) as total
            FROM DOACOES D
            JOIN USUARIOS U ON U.ID_USUARIOS = D.ID_USUARIOS
            GROUP BY U.NOME
            ORDER BY total DESC
            ROWS 5
        """)
        top_doadores = cur.fetchall()

        # Top 5 maiores engajadores (por curtidas)
        cur.execute("""
            SELECT U.NOME, COUNT(C.ID_CURTIDAS) as total
            FROM CURTIDAS C
            JOIN USUARIOS U ON U.ID_USUARIOS = C.ID_USUARIOS_DOADOR
            GROUP BY U.NOME
            ORDER BY total DESC
            ROWS 5
        """)
        top_curtidas = cur.fetchall()

        pdf = FPDF()
        pdf.add_page()

        header(pdf, "doadores")

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "RESUMO", ln=True)

        pdf.ln(5)

        resumo_3_colunas(pdf, [
            ("Total de doadores", total_doadores),
            ("Total de doações", total_doacoes),
            ("Valor arrecadado", f"R$ {total_valor:,.2f}".replace(",", ".").replace(".", ",", 1))
        ])

        # Só mostra o ranking se houver doadores
        if top_doadores:
            ranking_lista(pdf, "MAIORES DOADORES", top_doadores, tipo="moeda")
        else:
            pdf.set_font("Arial", "I", 10)
            pdf.cell(0, 6, "Nenhuma doação registrada", ln=True)
            pdf.ln(3)

        if top_curtidas:
            ranking_lista(pdf, "MAIORES ENGAJADORES", top_curtidas, tipo="numero")
        else:
            pdf.set_font("Arial", "I", 10)
            pdf.cell(0, 6, "Nenhum engajamento registrado", ln=True)
            pdf.ln(3)

        azul = (12, 89, 139)
        cinza = (120, 120, 120)

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "LISTA DE DOADORES", ln=True)

        pdf.ln(3)

        for u in usuarios:
            id_usuario, nome, cpf, email = u

            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*azul)
            pdf.cell(0, 6, nome, ln=True)

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"ID: {id_usuario}", ln=True)
            pdf.cell(0, 5, f"Email: {email}", ln=True)

            # Formatar CPF com máscara
            cpf_formatado = formatar_cpf(cpf) if cpf else "Não informado"
            pdf.cell(0, 5, f"CPF: {cpf_formatado}", ln=True)

            pdf.ln(5)

            pdf.set_draw_color(*cinza)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())

            pdf.ln(5)

        footer(pdf)

        pdf_path = "relatorio_doadores.pdf"
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'Relatorios')
        os.makedirs(caminho, exist_ok=True)
        caminho_pdf = os.path.join(caminho, pdf_path)
        pdf.output(caminho_pdf)

        return send_file(caminho_pdf, as_attachment=True)

    except Exception as e:
        print(f"ERRO relatorio_doadores: {e}")
        con.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()
        con.close()




@app.route('/admin/relatorio_ongs', methods=['GET'])
def relatorio_ongs():

    con = conexao()
    cur = con.cursor()

    try:
        # Buscar TODAS as ONGs para a lista completa
        cur.execute("""
            SELECT ID_USUARIOS, NOME, CPF_CNPJ, EMAIL
            FROM USUARIOS
            WHERE TIPO = 2
            ORDER BY NOME ASC
        """)
        ongs = cur.fetchall()

        if not ongs:
            return jsonify({'error': 'Nenhuma ONG encontrada'}), 404

        total_ongs = len(ongs)

        # Total arrecadado (todas as ONGs)
        cur.execute("SELECT COALESCE(SUM(VALOR), 0), COUNT(*) FROM DOACOES")
        retorno = cur.fetchone()
        total_valor = retorno[0]

        # Total de voluntariados
        cur.execute("""
            SELECT COUNT(V.ID_VOLUNTARIADO)
            FROM VOLUNTARIADO V
        """)
        total_voluntarios = cur.fetchone()[0]

        # Ranking ONGs por arrecadação (APENAS com valor > 0)
        cur.execute("""
            SELECT U.NOME, COALESCE(SUM(D.VALOR), 0) as total
            FROM USUARIOS U
            LEFT JOIN PROJETOS P ON P.ID_USUARIOS = U.ID_USUARIOS
            LEFT JOIN DOACOES D ON D.ID_PROJETOS = P.ID_PROJETOS
            WHERE U.TIPO = 2
            GROUP BY U.NOME
            HAVING COALESCE(SUM(D.VALOR), 0) > 0
            ORDER BY total DESC
            ROWS 5
        """)
        ongs_doacoes = cur.fetchall()

        # Ranking ONGs por voluntariados (APENAS com count > 0)
        cur.execute("""
            SELECT U.NOME, COUNT(V.ID_VOLUNTARIADO) as total
            FROM USUARIOS U
            LEFT JOIN PROJETOS P ON P.ID_USUARIOS = U.ID_USUARIOS
            LEFT JOIN VOLUNTARIADO V ON V.ID_PROJETOS = P.ID_PROJETOS
            WHERE U.TIPO = 2
            GROUP BY U.NOME
            HAVING COUNT(V.ID_VOLUNTARIADO) > 0
            ORDER BY total DESC
            ROWS 5
        """)
        ongs_voluntariado = cur.fetchall()

        # Lista detalhada de TODAS as ONGs (incluindo as com 0)
        cur.execute("""
            SELECT 
                U.ID_USUARIOS,
                U.NOME,
                U.CPF_CNPJ,
                U.EMAIL,
                COUNT(DISTINCT D.ID_DOACOES) as QTD_DOACOES,
                COALESCE(SUM(D.VALOR), 0) as TOTAL_DOACOES,
                COUNT(DISTINCT V.ID_VOLUNTARIADO) as QTD_VOLUNTARIADOS
            FROM USUARIOS U
            LEFT JOIN PROJETOS P ON P.ID_USUARIOS = U.ID_USUARIOS
            LEFT JOIN DOACOES D ON D.ID_PROJETOS = P.ID_PROJETOS
            LEFT JOIN VOLUNTARIADO V ON V.ID_PROJETOS = P.ID_PROJETOS
            WHERE U.TIPO = 2
            GROUP BY U.ID_USUARIOS, U.NOME, U.CPF_CNPJ, U.EMAIL
            ORDER BY U.ID_USUARIOS ASC
        """)
        lista_ongs = cur.fetchall()

        pdf = FPDF()
        pdf.add_page()

        header(pdf, "ONGs")

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "RESUMO DAS ONGs", ln=True)

        pdf.ln(5)

        resumo_3_colunas(pdf, [
            ("Total de ONGs", total_ongs),
            ("Arrecadado", f"R$ {total_valor:,.2f}".replace(",", ".").replace(".", ",", 1)),
            ("Voluntários", total_voluntarios)
        ])

        # Só mostra o ranking se houver ONGs com doações
        if ongs_doacoes:
            ranking_lista(pdf, "ONGS COM MAIOR ARRECADAÇÃO", ongs_doacoes, tipo="moeda")
        else:
            pdf.set_font("Arial", "I", 10)
            pdf.cell(0, 6, "Nenhuma ONG com arrecadação registrada", ln=True)
            pdf.ln(3)

        # Só mostra o ranking se houver ONGs com voluntariados
        if ongs_voluntariado:
            ranking_lista(pdf, "ONGS COM MAIS PEDIDOS DE VOLUNTARIADO", ongs_voluntariado, tipo="voluntariado")
        else:
            pdf.set_font("Arial", "I", 10)
            pdf.cell(0, 6, "Nenhuma ONG com voluntariado registrado", ln=True)
            pdf.ln(3)

        azul = (12, 89, 139)
        cinza = (120, 120, 120)

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "LISTA COMPLETA DE ONGs", ln=True)

        pdf.ln(3)

        for ong in lista_ongs:
            id_ong, nome, cnpj, email, qtd_doacoes, total_ong, qtd_voluntarios = ong

            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*azul)
            pdf.cell(0, 6, nome, ln=True)

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"ID: {id_ong}", ln=True)
            pdf.cell(0, 5, f"Email: {email}", ln=True)

            # Formatar CNPJ com máscara ##.###.###/####-##
            cnpj_formatado = formatar_cnpj(cnpj) if cnpj else "Não informado"
            pdf.cell(0, 5, f"CNPJ: {cnpj_formatado}", ln=True)

            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Doações: {qtd_doacoes}", ln=True)
            pdf.cell(0, 5, f"Voluntários: {qtd_voluntarios}", ln=True)

            pdf.cell(
                0, 5,
                f"Total arrecadado: R$ {total_ong:,.2f}".replace(",", ".").replace(".", ",", 1),
                ln=True
            )

            pdf.ln(5)

            pdf.set_draw_color(*cinza)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())

            pdf.ln(5)

        footer(pdf)

        pdf_path = "relatorio_ongs.pdf"
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'Relatorios')
        os.makedirs(caminho, exist_ok=True)
        caminho_pdf = os.path.join(caminho, pdf_path)
        pdf.output(caminho_pdf)

        return send_file(caminho_pdf, as_attachment=True)

    except Exception as e:
        print(f"ERRO relatorio_ongs: {e}")
        con.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()
        con.close()


@app.route('/admin/relatorio_doacoes_periodo', methods=['POST'])
def relatorio_doacoes_periodo():
    """Gera relatório PDF de doações em um período específico"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 0:
        return jsonify({'error': 'Apenas administradores podem acessar'}), 403

    data = request.get_json()
    data_inicio = data.get('data_inicio')
    data_fim = data.get('data_fim')

    if not data_inicio or not data_fim:
        return jsonify({'error': 'Datas de início e fim são obrigatórias'}), 400

    con = conexao()
    cur = con.cursor()

    try:
        # Converter datas para formato Firebird
        data_inicio_formatada = data_inicio.replace('-', '/')
        data_fim_formatada = data_fim.replace('-', '/')

        cur.execute("""
            SELECT 
                d.ID_DOACOES,
                u_ong.NOME as ONG_NOME,
                u_doador.NOME as DOADOR_NOME,
                p.TITULO as PROJETO,
                d.VALOR,
                d.DATA_DOACAO
            FROM DOACOES d
            INNER JOIN PROJETOS p ON d.ID_PROJETOS = p.ID_PROJETOS
            INNER JOIN USUARIOS u_ong ON p.ID_USUARIOS = u_ong.ID_USUARIOS
            INNER JOIN USUARIOS u_doador ON d.ID_USUARIOS = u_doador.ID_USUARIOS
            WHERE d.DATA_DOACAO BETWEEN ? AND ?
            ORDER BY d.DATA_DOACAO ASC
        """, (data_inicio_formatada, data_fim_formatada))
        doacoes = cur.fetchall()

        if not doacoes:
            return jsonify({'error': 'Nenhuma doação encontrada no período'}), 404

        total_doacoes = len(doacoes)
        total_valor = sum(d[4] for d in doacoes)

        # Estatísticas por ONG
        ongs_dict = {}
        for d in doacoes:
            ong_nome = d[1]
            if ong_nome not in ongs_dict:
                ongs_dict[ong_nome] = {'quantidade': 0, 'valor': 0}
            ongs_dict[ong_nome]['quantidade'] += 1
            ongs_dict[ong_nome]['valor'] += d[4]

        top_ongs = sorted(ongs_dict.items(), key=lambda x: x[1]['valor'], reverse=True)[:5]

        # Estatísticas por doador
        doadores_dict = {}
        for d in doacoes:
            doador_nome = d[2]
            if doador_nome not in doadores_dict:
                doadores_dict[doador_nome] = {'quantidade': 0, 'valor': 0}
            doadores_dict[doador_nome]['quantidade'] += 1
            doadores_dict[doador_nome]['valor'] += d[4]

        top_doadores = sorted(doadores_dict.items(), key=lambda x: x[1]['valor'], reverse=True)[:5]

        pdf = FPDF()
        pdf.add_page()

        header(pdf, "Doações no Período")

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "RESUMO DO PERÍODO", ln=True)

        pdf.ln(5)

        resumo_3_colunas(pdf, [
            ("Total de doações", total_doacoes),
            ("Valor total", f"R$ {total_valor:,.2f}".replace(",", ".").replace(".", ",", 1)),
            ("Média por doação", f"R$ {total_valor / total_doacoes:,.2f}".replace(",", ".").replace(".", ",", 1))
        ])

        # Converter top_ongs para o formato que a função ranking_lista espera
        top_ongs_lista = [(nome, dados['valor']) for nome, dados in top_ongs]
        ranking_lista(pdf, "ONGS COM MAIOR ARRECADAÇÃO", top_ongs_lista, tipo="moeda")

        # Converter top_doadores para o formato que a função ranking_lista espera
        top_doadores_lista = [(nome, dados['valor']) for nome, dados in top_doadores]
        ranking_lista(pdf, "MAIORES DOADORES", top_doadores_lista, tipo="moeda")

        azul = (12, 89, 139)
        cinza = (120, 120, 120)

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "LISTA DE DOAÇÕES", ln=True)

        pdf.ln(3)

        for doacao in doacoes:
            id_doacao, ong_nome, doador_nome, projeto, valor, data_doacao = doacao

            # Formatar data
            if hasattr(data_doacao, 'strftime'):
                data_str = data_doacao.strftime('%d/%m/%Y')
            else:
                data_str = str(data_doacao)

            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*azul)
            pdf.cell(0, 6, f"Doação #{id_doacao}", ln=True)

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Data: {data_str}", ln=True)
            pdf.cell(0, 5, f"Doador: {doador_nome}", ln=True)
            pdf.cell(0, 5, f"ONG: {ong_nome}", ln=True)
            pdf.cell(0, 5, f"Projeto: {projeto}", ln=True)
            pdf.cell(0, 5, f"Valor: R$ {valor:,.2f}".replace(",", ".").replace(".", ",", 1), ln=True)

            pdf.ln(5)

            pdf.set_draw_color(*cinza)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())

            pdf.ln(5)

        footer(pdf)

        pdf_path = f"relatorio_doacoes_{data_inicio}_a_{data_fim}.pdf"
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'Relatorios')
        os.makedirs(caminho, exist_ok=True)
        caminho_pdf = os.path.join(caminho, pdf_path)
        pdf.output(caminho_pdf)

        return send_file(caminho_pdf, as_attachment=True)

    except Exception as e:
        con.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()
        con.close()


