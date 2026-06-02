
from flask import jsonify, request, Response, send_file
from main import app
from db import conexao
from funcao import decodificar_token, formatar_cpf, footer, header, resumo_3_colunas, ranking_lista, formatar_cnpj

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
                'valor': f'R$ {float(d[0]):.2f}'.replace('.', ','),
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
        # Buscar todas as doações e processar os meses em Python
        cur.execute("""
            SELECT DATA_DOACAO
            FROM DOACOES
            WHERE ID_USUARIOS = ?
            ORDER BY DATA_DOACAO
        """, (id_doador,))
        doacoes = cur.fetchall()

        meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        dados_meses = {mes: 0 for mes in meses}

        for doacao in doacoes:
            if doacao[0]:
                try:
                    mes = doacao[0].month
                    dados_meses[meses[mes - 1]] += 1
                except:
                    pass

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
        # Buscar todas as doações da ONG e processar em Python
        cur.execute("""
            SELECT d.VALOR, d.DATA_DOACAO
            FROM DOACOES d
            INNER JOIN PROJETOS p ON d.ID_PROJETOS = p.ID_PROJETOS
            WHERE p.ID_USUARIOS = ?
            ORDER BY d.DATA_DOACAO
        """, (id_ong,))
        doacoes = cur.fetchall()

        meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        dados_meses = {mes: 0 for mes in meses}

        for doacao in doacoes:
            valor = doacao[0] if doacao[0] else 0
            data = doacao[1]
            if data:
                try:
                    mes = data.month
                    dados_meses[meses[mes - 1]] += float(valor)
                except:
                    pass

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
        # Buscar todas as doações e processar em Python
        cur.execute("""
            SELECT VALOR, DATA_DOACAO
            FROM DOACOES
            ORDER BY DATA_DOACAO
        """)
        doacoes = cur.fetchall()

        meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        dados_meses = {mes: 0 for mes in meses}

        for doacao in doacoes:
            valor = doacao[0] if doacao[0] else 0
            data = doacao[1]
            if data:
                try:
                    mes = data.month
                    dados_meses[meses[mes - 1]] += float(valor)
                except:
                    pass

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
        # Lista de doadores em ordem crescent por ID
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

        # CORREÇÃO: Usar COALESCE com CAST para evitar erro de SQLDA no Firebird
        cur.execute("""
            SELECT 
                CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION) as TOTAL_VALOR, 
                COUNT(*) as TOTAL_DOACOES 
            FROM DOACOES
        """)
        resultado = cur.fetchone()

        # Tratar possíveis valores NULL
        total_valor = float(resultado[0]) if resultado and resultado[0] is not None else 0
        total_doacoes = int(resultado[1]) if resultado and resultado[1] is not None else 0

        # Top 5 maiores doadores (por valor) - usando ROWS no Firebird com CAST corrigido
        cur.execute("""
            SELECT FIRST 5 U.NOME, CAST(COALESCE(SUM(D.VALOR), 0) AS DOUBLE PRECISION) as total
            FROM DOACOES D
            JOIN USUARIOS U ON U.ID_USUARIOS = D.ID_USUARIOS
            GROUP BY U.NOME
            ORDER BY total DESC
        """)
        top_doadores = cur.fetchall()

        # Top 5 maiores engajadores (por curtidas)
        cur.execute("""
            SELECT FIRST 5 U.NOME, COUNT(C.ID_CURTIDAS) as total
            FROM CURTIDAS C
            JOIN USUARIOS U ON U.ID_USUARIOS = C.ID_USUARIOS_DOADOR
            GROUP BY U.NOME
            ORDER BY total DESC
        """)
        top_curtidas = cur.fetchall()

        pdf = FPDF()
        pdf.add_page()

        header(pdf, "doadores")

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "RESUMO", ln=True)

        pdf.ln(5)

        # Formatar valores
        valor_formatado = f"R$ {total_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        resumo_3_colunas(pdf, [
            ("Total de doadores", total_doadores),
            ("Total de doações", total_doacoes),
            ("Valor arrecadado", valor_formatado)
        ])

        # Só mostra o ranking se houver doadores
        if top_doadores and len(top_doadores) > 0:
            # Converter para lista de tuplas (nome, valor)
            top_doadores_lista = [(row[0], float(row[1])) for row in top_doadores if row[1] > 0]
            if top_doadores_lista:
                ranking_lista(pdf, "MAIORES DOADORES", top_doadores_lista, tipo="moeda")
        else:
            pdf.set_font("Arial", "I", 10)
            pdf.cell(0, 6, "Nenhuma doação registrada", ln=True)
            pdf.ln(3)

        if top_curtidas and len(top_curtidas) > 0:
            top_curtidas_lista = [(row[0], int(row[1])) for row in top_curtidas if row[1] > 0]
            if top_curtidas_lista:
                ranking_lista(pdf, "MAIORES ENGAJADORES", top_curtidas_lista, tipo="numero")
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
            # Garantir que temos 4 campos
            id_usuario = u[0] if u[0] is not None else 0
            nome = u[1] if u[1] is not None else "Não informado"
            cpf = u[2] if u[2] is not None else ""
            email = u[3] if u[3] is not None else "Não informado"

            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*azul)
            pdf.cell(0, 6, str(nome), ln=True)

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"ID: {id_usuario}", ln=True)
            pdf.cell(0, 5, f"Email: {email}", ln=True)

            # Formatar CPF com máscara
            cpf_formatado = formatar_cpf(cpf) if cpf and cpf != "" else "Não informado"
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()
        con.close()



@app.route('/admin/relatorio_ongs', methods=['GET'])
def relatorio_ongs():

    con = conexao()
    cur = con.cursor()

    try:

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

        # Total arrecadado (todas as ONGs) - Corrigido com CAST para evitar erro de SQLDA
        cur.execute("""
            SELECT 
                CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION) as TOTAL_VALOR, 
                COUNT(*) as TOTAL_DOACOES 
            FROM DOACOES
        """)
        resultado = cur.fetchone()
        total_valor = float(resultado[0]) if resultado and resultado[0] is not None else 0

        # Total de voluntariados
        cur.execute("SELECT COUNT(ID_VOLUNTARIADO) FROM VOLUNTARIADO")
        total_voluntarios = cur.fetchone()[0] or 0

        # Ranking ONGs por arrecadação (APENAS com valor > 0) - Corrigido com CAST
        cur.execute("""
            SELECT FIRST 5 U.NOME, CAST(COALESCE(SUM(D.VALOR), 0) AS DOUBLE PRECISION) as total
            FROM USUARIOS U
            LEFT JOIN PROJETOS P ON P.ID_USUARIOS = U.ID_USUARIOS
            LEFT JOIN DOACOES D ON D.ID_PROJETOS = P.ID_PROJETOS
            WHERE U.TIPO = 2
            GROUP BY U.NOME
            HAVING CAST(COALESCE(SUM(D.VALOR), 0) AS DOUBLE PRECISION) > 0
            ORDER BY total DESC
        """)
        ongs_doacoes = cur.fetchall()

        # Ranking ONGs por voluntariados (APENAS com count > 0)
        cur.execute("""
            SELECT FIRST 5 
                U.NOME,
                COUNT(DISTINCT V.ID_VOLUNTARIADO) as QTD_VOLUNTARIADOS
            FROM USUARIOS U
            LEFT JOIN PROJETOS P ON P.ID_USUARIOS = U.ID_USUARIOS
            LEFT JOIN VOLUNTARIADO V ON V.ID_PROJETOS = P.ID_PROJETOS
            WHERE U.TIPO = 2
            GROUP BY U.NOME
            HAVING COUNT(DISTINCT V.ID_VOLUNTARIADO) > 0
            ORDER BY QTD_VOLUNTARIADOS DESC
        """)
        ongs_voluntariado = cur.fetchall()

        # Lista completa de ONGs com estatísticas - Corrigido com CAST
        cur.execute("""
            SELECT 
                U.ID_USUARIOS,
                U.NOME,
                U.CPF_CNPJ,
                U.EMAIL,
                COUNT(DISTINCT D.ID_DOACOES) as QTD_DOACOES,
                CAST(COALESCE(SUM(D.VALOR), 0) AS DOUBLE PRECISION) as TOTAL_DOACOES,
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

        # Formatar valor
        valor_formatado = f"R$ {total_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        resumo_3_colunas(pdf, [
            ("Total de ONGs", total_ongs),
            ("Arrecadado", valor_formatado),
            ("Voluntários", total_voluntarios)
        ])

        # Só mostra o ranking se houver ONGs com doações
        if ongs_doacoes and len(ongs_doacoes) > 0:
            ongs_doacoes_lista = [(row[0], float(row[1])) for row in ongs_doacoes if row[1] > 0]
            if ongs_doacoes_lista:
                ranking_lista(pdf, "ONGS COM MAIOR ARRECADAÇÃO", ongs_doacoes_lista, tipo="moeda")
        else:
            pdf.set_font("Arial", "I", 10)
            pdf.cell(0, 6, "Nenhuma ONG com arrecadação registrada", ln=True)
            pdf.ln(3)

        # Só mostra o ranking se houver ONGs com voluntariados
        if ongs_voluntariado and len(ongs_voluntariado) > 0:
            ongs_voluntariado_lista = [(row[0], int(row[1])) for row in ongs_voluntariado if row[1] > 0]
            if ongs_voluntariado_lista:
                ranking_lista(pdf, "ONGS COM MAIS PEDIDOS DE VOLUNTARIADO", ongs_voluntariado_lista, tipo="voluntariado")
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
            # Garantir que temos todos os campos
            id_ong = ong[0] if ong[0] is not None else 0
            nome = ong[1] if ong[1] is not None else "Não informado"
            cnpj = ong[2] if ong[2] is not None else ""
            email = ong[3] if ong[3] is not None else "Não informado"
            qtd_doacoes = int(ong[4]) if ong[4] is not None else 0
            total_ong = float(ong[5]) if ong[5] is not None else 0
            qtd_voluntarios = int(ong[6]) if ong[6] is not None else 0

            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*azul)
            pdf.cell(0, 6, str(nome), ln=True)

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"ID: {id_ong}", ln=True)
            pdf.cell(0, 5, f"Email: {email}", ln=True)

            # Formatar CNPJ com máscara ##.###.###/####-##
            cnpj_formatado = formatar_cnpj(cnpj) if cnpj and cnpj != "" else "Não informado"
            pdf.cell(0, 5, f"CNPJ: {cnpj_formatado}", ln=True)

            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Doações: {qtd_doacoes}", ln=True)
            pdf.cell(0, 5, f"Voluntários: {qtd_voluntarios}", ln=True)

            total_ong_formatado = f"R$ {total_ong:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            pdf.cell(0, 5, f"Total arrecadado: {total_ong_formatado}", ln=True)

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
        import traceback
        traceback.print_exc()
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


# ============================================
# RELATÓRIO PARA O DOADOR
# ============================================
@app.route('/doador/meu_relatorio', methods=['GET'])
def doador_meu_relatorio():
    """Gera relatório PDF das doações do doador logado"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 1:
        return jsonify({'error': 'Apenas doadores podem acessar'}), 403

    id_doador = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        # Buscar dados do doador
        cur.execute("SELECT NOME, EMAIL, CPF_CNPJ FROM USUARIOS WHERE ID_USUARIOS = ?", (id_doador,))
        doador = cur.fetchone()
        nome_doador = doador[0] if doador else "Doador"
        email_doador = doador[1] if doador else ""
        cpf_doador = doador[2] if doador else ""

        # Buscar doações do doador
        cur.execute("""
            SELECT 
                d.ID_DOACOES,
                u_ong.NOME as ONG_NOME,
                p.TITULO as PROJETO,
                d.VALOR,
                d.DATA_DOACAO
            FROM DOACOES d
            INNER JOIN PROJETOS p ON d.ID_PROJETOS = p.ID_PROJETOS
            INNER JOIN USUARIOS u_ong ON p.ID_USUARIOS = u_ong.ID_USUARIOS
            WHERE d.ID_USUARIOS = ?
            ORDER BY d.DATA_DOACAO DESC
        """, (id_doador,))
        doacoes = cur.fetchall()

        # Estatísticas
        total_doacoes = len(doacoes)
        total_valor = sum(d[3] for d in doacoes) if doacoes else 0

        # Agrupar por ONG
        ongs_dict = {}
        for d in doacoes:
            ong_nome = d[1]
            if ong_nome not in ongs_dict:
                ongs_dict[ong_nome] = {'quantidade': 0, 'valor': 0}
            ongs_dict[ong_nome]['quantidade'] += 1
            ongs_dict[ong_nome]['valor'] += d[3]

        top_ongs = sorted(ongs_dict.items(), key=lambda x: x[1]['valor'], reverse=True)[:5]

        pdf = FPDF()
        pdf.add_page()

        # Adicionar logo
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'Empresas', 'logo_1.jpeg')
        if os.path.exists(logo_path):
            pdf.image(logo_path, x=10, y=8, w=30)

        header(pdf, "Minhas Doações")

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "RESUMO", ln=True)
        pdf.ln(5)

        resumo_3_colunas(pdf, [
            ("Total de doações", total_doacoes),
            ("Valor total doado", f"R$ {total_valor:,.2f}".replace(",", ".").replace(".", ",", 1)),
            ("Média por doação", f"R$ {total_valor / total_doacoes:,.2f}".replace(",", ".").replace(".", ",",
                                                                                                    1) if total_doacoes > 0 else "R$ 0,00")
        ])

        if top_ongs:
            ranking_lista(pdf, "ONGS QUE MAIS RECEBERAM", [(nome, dados['valor']) for nome, dados in top_ongs],
                          tipo="moeda")

        azul = (12, 89, 139)
        cinza = (120, 120, 120)

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "MINHAS DOAÇÕES", ln=True)
        pdf.ln(3)

        for doacao in doacoes:
            id_doacao, ong_nome, projeto, valor, data_doacao = doacao

            data_str = data_doacao.strftime('%d/%m/%Y') if hasattr(data_doacao, 'strftime') else str(data_doacao)

            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*azul)
            pdf.cell(0, 6, f"Doação para {ong_nome}", ln=True)

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Data: {data_str}", ln=True)
            pdf.cell(0, 5, f"Projeto: {projeto}", ln=True)
            pdf.cell(0, 5, f"Valor: R$ {float(valor):,.2f}".replace(",", ".").replace(".", ",", 1), ln=True)

            pdf.ln(5)
            pdf.set_draw_color(*cinza)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)

        footer(pdf)

        pdf_path = f"relatorio_doador_{id_doador}.pdf"
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'Relatorios')
        os.makedirs(caminho, exist_ok=True)
        caminho_pdf = os.path.join(caminho, pdf_path)
        pdf.output(caminho_pdf)

        return send_file(caminho_pdf, as_attachment=True)

    except Exception as e:
        print(f"ERRO doador_meu_relatorio: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()


# ============================================
# RELATÓRIO PARA A ONG
# ============================================
@app.route('/ong/meu_relatorio', methods=['GET'])
def ong_meu_relatorio():
    """Gera relatório PDF das doações recebidas pela ONG logada"""
    token_data = decodificar_token()
    if token_data == False:
        return jsonify({'error': 'Token necessário'}), 401
    if token_data['tipo'] != 2:
        return jsonify({'error': 'Apenas ONGs podem acessar'}), 403

    id_ong = token_data['id_usuarios']

    con = conexao()
    cur = con.cursor()

    try:
        # Buscar dados da ONG
        cur.execute("SELECT NOME, EMAIL, CPF_CNPJ FROM USUARIOS WHERE ID_USUARIOS = ?", (id_ong,))
        ong = cur.fetchone()
        nome_ong = ong[0] if ong else "ONG"
        email_ong = ong[1] if ong else ""
        cnpj_ong = ong[2] if ong else ""

        # Buscar doações recebidas pela ONG
        cur.execute("""
            SELECT 
                d.ID_DOACOES,
                u_doador.NOME as DOADOR_NOME,
                p.TITULO as PROJETO,
                d.VALOR,
                d.DATA_DOACAO
            FROM DOACOES d
            INNER JOIN PROJETOS p ON d.ID_PROJETOS = p.ID_PROJETOS
            INNER JOIN USUARIOS u_doador ON d.ID_USUARIOS = u_doador.ID_USUARIOS
            WHERE p.ID_USUARIOS = ?
            ORDER BY d.DATA_DOACAO DESC
        """, (id_ong,))
        doacoes = cur.fetchall()

        # Estatísticas
        total_doacoes = len(doacoes)
        total_valor = sum(d[3] for d in doacoes) if doacoes else 0

        # Agrupar por doador
        doadores_dict = {}
        for d in doacoes:
            doador_nome = d[1]
            if doador_nome not in doadores_dict:
                doadores_dict[doador_nome] = {'quantidade': 0, 'valor': 0}
            doadores_dict[doador_nome]['quantidade'] += 1
            doadores_dict[doador_nome]['valor'] += d[3]

        top_doadores = sorted(doadores_dict.items(), key=lambda x: x[1]['valor'], reverse=True)[:5]

        # Agrupar por projeto
        projetos_dict = {}
        for d in doacoes:
            projeto_nome = d[2]
            if projeto_nome not in projetos_dict:
                projetos_dict[projeto_nome] = {'quantidade': 0, 'valor': 0}
            projetos_dict[projeto_nome]['quantidade'] += 1
            projetos_dict[projeto_nome]['valor'] += d[3]

        top_projetos = sorted(projetos_dict.items(), key=lambda x: x[1]['valor'], reverse=True)[:5]

        pdf = FPDF()
        pdf.add_page()

        # Adicionar logo
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'Empresas', 'logo_1.jpeg')
        if os.path.exists(logo_path):
            pdf.image(logo_path, x=10, y=8, w=30)

        header(pdf, "Minhas Doações Recebidas")

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "RESUMO", ln=True)
        pdf.ln(5)

        resumo_3_colunas(pdf, [
            ("Total de doações", total_doacoes),
            ("Valor total recebido", f"R$ {total_valor:,.2f}".replace(",", ".").replace(".", ",", 1)),
            ("Média por doação", f"R$ {total_valor / total_doacoes:,.2f}".replace(",", ".").replace(".", ",",
                                                                                                    1) if total_doacoes > 0 else "R$ 0,00")
        ])

        if top_doadores:
            ranking_lista(pdf, "MAIORES DOADORES", [(nome, dados['valor']) for nome, dados in top_doadores],
                          tipo="moeda")

        if top_projetos:
            ranking_lista(pdf, "PROJETOS MAIS DOADOS", [(nome, dados['valor']) for nome, dados in top_projetos],
                          tipo="moeda")

        azul = (12, 89, 139)
        cinza = (120, 120, 120)

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, "LISTA DE DOAÇÕES RECEBIDAS", ln=True)
        pdf.ln(3)

        for doacao in doacoes:
            id_doacao, doador_nome, projeto, valor, data_doacao = doacao

            data_str = data_doacao.strftime('%d/%m/%Y') if hasattr(data_doacao, 'strftime') else str(data_doacao)

            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*azul)
            pdf.cell(0, 6, f"Doação de {doador_nome}", ln=True)

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Data: {data_str}", ln=True)
            pdf.cell(0, 5, f"Projeto: {projeto}", ln=True)
            pdf.cell(0, 5, f"Valor: R$ {float(valor):,.2f}".replace(",", ".").replace(".", ",", 1), ln=True)

            pdf.ln(5)
            pdf.set_draw_color(*cinza)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)

        footer(pdf)

        pdf_path = f"relatorio_ong_{id_ong}.pdf"
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'Relatorios')
        os.makedirs(caminho, exist_ok=True)
        caminho_pdf = os.path.join(caminho, pdf_path)
        pdf.output(caminho_pdf)

        return send_file(caminho_pdf, as_attachment=True)

    except Exception as e:
        print(f"ERRO ong_meu_relatorio: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        con.close()

