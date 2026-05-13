from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
import pymysql
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from rendimentos import app
from rendimentos.models import get_users
from rendimentos.config import conectar_bd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import os
from flask import current_app
from reportlab.platypus import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import smtplib
from email.mime.text import MIMEText

# Login Obrigatório
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:    
            flash('Login necessário', 'warning')
            return redirect(url_for('login'))  
        return f(*args, **kwargs)
    return decorated_function

# Cargo
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'cargo' not in session or session['cargo'] != 'Admin':
            flash('Acesso restrito aos administradores.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = get_users(username)
        if user is None:
            flash('Nome de utilizador não encontrado.', 'danger')
            return redirect(url_for('login'))

        if check_password_hash(user['pass'], password):
            flash('Login bem-sucedido!', 'success')
            session['user_id'] = user['idutilizador']
            session['utilizador'] = user['utilizador']
            session['cargo'] = user['cargo']
            session.permanent = True  
            return redirect(url_for('index'))
        else:
            flash('Senha incorreta.', 'danger')
    return render_template('login.html')

# Criara uma nova conta
@app.route('/nova_conta', methods=['GET', 'POST'])
def nova_conta():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash("Preencha todos os campos!", "error") #ERRO de falta de Preencha dos campos 
            return redirect(url_for('nova_conta'))

        hashed_password = generate_password_hash(password)

        cargo = "Admin" if username == "Rodrigo" else "Utilizador"

        con = conectar_bd()
        cursor = con.cursor()
        try:
            cursor.execute("INSERT INTO utilizadores (utilizador, pass, cargo) VALUES (%s, %s, %s)",
            (username, hashed_password, cargo))
            con.commit()
            flash("Conta criada com sucesso!", "success")
        except Exception as e:
            flash(f"Erro ao criar conta: {e}", "error")
        finally:
            cursor.close()
            con.close()

        return redirect(url_for('login'))
    return render_template('nova_conta.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Sessão encerrada!", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    dados_template = {}
    conn = None
    try:
        conn = conectar_bd()
        if conn and conn.is_connected():
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SHOW TABLES LIKE 'editar'")
                if cursor.fetchone():
                    cursor.execute("SELECT titulo, imagem FROM editar LIMIT 1")
                    dados = cursor.fetchone()
                    if dados:
                        dados_template['titulo'] = dados.get('titulo', 'GESTOR')
                        dados_template['imagem_logo'] = dados.get('imagem', 'assets/img/logo.png')
                else:
                    print("Tabela 'editar' não encontrada no base de dados")
                    
    except Exception as e:
        print(f"Erro ao acessar o base de dados: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()
    
    return render_template('Index.html', **dados_template)

@app.route('/editar_site', methods=['GET', 'POST'])
@admin_required
def editar_site():
    conn = conectar_bd()
    cursor = conn.cursor(dictionary=True)
    
    img_folder = os.path.join(current_app.root_path, 'static', 'assets', 'img')
    imagens = [f for f in os.listdir(img_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        imagem = request.form['imagem']
        
        cursor.execute("UPDATE editar SET titulo = %s, imagem = %s WHERE id = 1", 
                    (titulo, f"assets/img/{imagem}"))
        conn.commit()
        flash("Site atualizado com sucesso!", "success")
        return redirect(url_for('index'))
    
    cursor.execute("SELECT titulo, imagem FROM editar WHERE id = 1")
    dados = cursor.fetchone()
    conn.close()
    
    imagem_atual = dados['imagem'].split('/')[-1] if dados['imagem'] else ''
    
    return render_template('editar_site.html', 
                        dados=dados,
                        imagens=imagens,
                        imagem_atual=imagem_atual)

#! So o administrador tem acesso 
@app.route('/definicoes', methods=['GET', 'POST'])
@login_required
def definicoes():
    conn = conectar_bd()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        id_utilizador = request.form.get('id_utilizador')
        novo_cargo = request.form.get('cargo')

        if id_utilizador and novo_cargo:
            cursor.execute("UPDATE utilizadores SET cargo = %s WHERE idutilizador = %s", (novo_cargo, id_utilizador))
            conn.commit()
            flash('Cargo atualizado com sucesso!', 'success')

    cursor.execute("SELECT idutilizador, utilizador, cargo FROM utilizadores")
    utilizadores = cursor.fetchall()

    conn.close()

    return render_template('Definicoes.html',utilizadores=utilizadores)

#! Gestor pessoal, gestor empresarial e definições
@app.route('/pagina_inicial')
@login_required
def pagina_inicial():
    conn = conectar_bd()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT utilizador FROM utilizadores  WHERE idutilizador = %s", (session['user_id'],))
    user = cursor.fetchone()

    conn.close()

    if user:
        nome = user['utilizador']
    else:
        nome = "Utilizador não encontrado"

    return render_template('Pagina_inicial.html', nome=nome)

#
@app.route('/rendimento_familiar')
@login_required
def rendimento_familiar():
    #Lista de meses cirada dinamicamente
    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    return render_template('Rendimento Familiar.html', meses=meses)

@app.route('/mes/<int:mes>')
@login_required
def visualizar_mes(mes):
    if 'user_id' not in session:
        flash("É necessário fazer login.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Mapeamento dos números dos meses para seus nomes
    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }

    nome_mes = meses_nomes.get(mes, "Desconhecido")  

    con = conectar_bd()
    cursor = con.cursor(dictionary=True)

    cursor.execute("SELECT valor, moeda FROM rendimentos WHERE idutilizador=%s AND mes=%s", (user_id, mes))
    rendimentos = cursor.fetchall()

    cursor.execute("""
        SELECT d.iddespesa, c.nome_categoria, d.valor, d.moeda 
        FROM despesas d 
        JOIN categorias c ON d.idcategoria = c.idcategoria 
        WHERE d.idutilizador=%s AND d.mes=%s
    """, (user_id, mes))
    despesas = cursor.fetchall()

    cursor.execute("SELECT * FROM categorias")
    categorias = cursor.fetchall()

    con.close()

    return render_template('mes.html', mes=mes, nome_mes=nome_mes, rendimentos=rendimentos, despesas=despesas, categorias=categorias)

@app.route('/adicionar_rendimento', methods=['POST'])
@login_required
def adicionar_rendimento():
    if 'user_id' not in session:
        flash("É necessário fazer login.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    valor = request.form['valor']
    moeda = request.form['moeda']
    mes = request.form['mes']

    con = conectar_bd()
    cursor = con.cursor()
    cursor.execute("INSERT INTO rendimentos (idutilizador, mes, valor, moeda) VALUES (%s, %s, %s, %s)",
                   (user_id, mes, valor, moeda))
    con.commit()
    con.close()

    flash("Rendimento adicionado com sucesso!", "success")
    return redirect(url_for('visualizar_mes', mes=mes))


@app.route('/adicionar_despesa', methods=['POST'])
@login_required
def adicionar_despesa():
    if 'user_id' not in session:
        flash("É necessário fazer login.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    idcategoria = request.form['idsubcategoria']
    valor = request.form['valor']
    moeda = request.form['moeda']
    mes = request.form['mes']

    con = conectar_bd()
    cursor = con.cursor()
    cursor.execute("INSERT INTO despesas (idutilizador, mes, idcategoria, valor, moeda) VALUES (%s, %s, %s, %s, %s)",
                   (user_id, mes, idcategoria, valor, moeda))
    con.commit()
    con.close()

    flash("Despesa adicionada com sucesso!", "success")
    return redirect(url_for('visualizar_mes', mes=mes))




# Rota para página de Rendimento Familiar
@app.route('/despesas_anuais')
@login_required
def despesas_anuais():
    user_id = session['user_id']

    con = conectar_bd()
    cursor = con.cursor(dictionary=True)

    cursor.execute("""
        SELECT mes, SUM(valor) as total
        FROM despesas
        WHERE idutilizador = %s AND ano = YEAR(CURDATE())
        GROUP BY mes
        ORDER BY mes
    """, (user_id,))

    despesas = {mes: 0 for mes in range(1, 13)}  # Inicializa os meses sempre com 0€
    for row in cursor.fetchall():
        despesas[row["mes"]] = row["total"]

    con.close()

    return render_template('Despesas_Anuais.html', despesas=despesas)

# Gestor Empresarial
@app.route('/stock')
@login_required
def stock():
    con = conectar_bd()
    cursor = con.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT s.*, u.utilizador 
        FROM stock s 
        LEFT JOIN utilizadores u ON s.idutilizador = u.idutilizador 
        ORDER BY s.data DESC
    """)
    operacoes = cursor.fetchall()
    
    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()
    
    cursor.close()
    con.close()
    
    return render_template('Stock.html', operacoes=operacoes, produtos=produtos)

@app.route('/categorias')
@login_required
def categorias():
    con = conectar_bd()
    cursor = con.cursor(dictionary=True)

    cursor.execute("SELECT * FROM categorias")
    categorias = cursor.fetchall()

    cursor.close()
    con.close()
    return render_template('categorias.html', categorias=categorias)
    
@app.route('/adicionar_categoria', methods=['GET', 'POST'])
@login_required
def adicionar_categoria():
    if request.method == 'POST':
        nome_categoria = request.form['nome_categoria']
        
        con = conectar_bd()
        cursor = con.cursor()
        try:
            cursor.execute("INSERT INTO categorias (nome_categoria) VALUES (%s)", (nome_categoria,))
            con.commit()
            flash("Categoria adicionada com sucesso!", "success")
        except Exception as e:
            con.rollback()
            flash(f"Erro ao adicionar categoria: {e}", "danger")
        finally:
            cursor.close()
            con.close()
        
        return redirect(url_for('categorias'))
    return render_template('adicionar_categoria.html')

@app.route('/editar_categoria/<int:idcategoria>', methods=['GET', 'POST'])
@login_required
def editar_categoria(idcategoria):
    con = conectar_bd()
    cursor = con.cursor(dictionary=True)

    cursor.execute("SELECT idcategoria, nome_categoria FROM categorias WHERE idcategoria = %s", (idcategoria,))
    categoria = cursor.fetchone()

    if request.method == 'POST':
        nome_categoria = request.form['nome_categoria']
        try:
            cursor.execute("UPDATE categorias SET nome_categoria = %s WHERE idcategoria = %s", (nome_categoria, idcategoria))
            con.commit()
            flash("Categoria atualizada com sucesso!", "success")
            return redirect(url_for('categorias'))
        except Exception as e:
            con.rollback()
            flash(f"Erro ao atualizar categoria: {e}", "danger")
    
    cursor.close()
    con.close()
    return render_template('editar_categoria.html', categoria=categoria)

@app.route('/eliminar_categoria/<int:idcategoria>', methods=['GET'])
@login_required
def eliminar_categoria(idcategoria):
    con = conectar_bd()
    cursor = con.cursor()

    try:
        cursor.execute("DELETE FROM categorias WHERE idcategoria = %s", (idcategoria,))
        con.commit()
        flash("Categoria eliminada com sucesso!", "success")
    except Exception as e:
        con.rollback()
        flash(f"Erro ao eliminar categoria: {e}", "danger")
    
    cursor.close()
    con.close()
    return redirect(url_for('categorias'))

@app.route('/adicionar_stock', methods=['GET', 'POST'])
@admin_required
def adicionar_stock():
    if request.method == 'POST':
        produto = request.form['produto']
        try:
            quantidade = int(request.form['quantidade'])
            stock_minimo = int(request.form.get('stock_minimo', 0)) 
        except ValueError:
            flash("Valores numéricos inválidos.", "danger")
            return redirect(url_for('adicionar_stock'))
        
        con = conectar_bd()
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO stock (idproduto, produto, quantidade, acao, idutilizador)
                VALUES (
                    (SELECT idproduto FROM produtos WHERE nome = %s),
                    %s, %s, 'adicionado', %s
                )
            """, (produto, produto, quantidade, session['user_id']))
            
            # Verifica se o produto já existe na tabela produtos
            cursor.execute("SELECT idproduto, quantidade, stock_minimo FROM produtos WHERE nome = %s", (produto,))
            produto_existente = cursor.fetchone()
            
            if produto_existente:
                novo_valor = produto_existente[1] + quantidade
                if stock_minimo > 0:
                    cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = %s, stock_minimo = %s 
                        WHERE idproduto = %s
                    """, (novo_valor, stock_minimo, produto_existente[0]))
                else:
                    cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = %s 
                        WHERE idproduto = %s
                    """, (novo_valor, produto_existente[0]))
            else:
                # Insere novo produto com quantidade e stock mínimo
                cursor.execute("""
                    INSERT INTO produtos (nome, quantidade, stock_minimo) 
                    VALUES (%s, %s, %s)
                """, (produto, quantidade, stock_minimo if stock_minimo > 0 else None))
            
            con.commit()
            flash("Stock adicionado com sucesso!", "success")
        except Exception as e:
            con.rollback()
            flash(f"Erro ao adicionar stock: {e}", "danger")
        finally:
            cursor.close()
            con.close()
        
        return redirect(url_for('stock'))
    return render_template('adicionar_stock.html')

@app.route('/repor_stock', methods=['GET', 'POST'])
@login_required
def repor_stock():
    con = conectar_bd()
    cursor = con.cursor(dictionary=True)
    
    if request.method == 'POST':
        produto = request.form['produto']
        try:
            quantidade = int(request.form['quantidade'])
        except ValueError:
            flash("Quantidade inválida.", "danger")
            return redirect(url_for('repor_stock'))
        
        try:
            # Verifica se o produto existe
            cursor.execute("SELECT idproduto, quantidade FROM produtos WHERE nome = %s", (produto,))
            produto_existente = cursor.fetchone()
            
            if not produto_existente:
                flash("Produto não encontrado no stock.", "danger")
                return redirect(url_for('repor_stock'))
            
            idproduto = produto_existente['idproduto']
            
            # Operação de reposição
            cursor.execute("""
                INSERT INTO stock (idproduto, produto, quantidade, acao, idutilizador)
                VALUES (%s, %s, %s, 'reposição', %s)
            """, (idproduto, produto, quantidade, session['user_id']))
            
            cursor.execute("""
                UPDATE produtos 
                SET quantidade = %s 
                WHERE idproduto = %s
            """, (quantidade, idproduto))
            
            con.commit()
            flash("Stock reposto com sucesso!", "success")
        except Exception as e:
            con.rollback()
            flash(f"Erro ao repor stock: {e}", "danger")
        finally:
            cursor.close()
            con.close()
        
        return redirect(url_for('stock'))
    
    else:  
        try:
            cursor.execute("SELECT * FROM produtos")
            produtos = cursor.fetchall()
        except Exception as e:
            flash(f"Erro ao carregar os produtos: {e}", "danger")
            produtos = []
        finally:
            cursor.close()
            con.close()
        
        return render_template('repor_stock.html', produtos=produtos)
        
@app.route('/retirar_stock', methods=['GET', 'POST'])
@login_required
def retirar_stock():
    con = conectar_bd()
    cursor = con.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Procura o nome do produto selecionado
        produto = request.form['produto']
        try:
            quantidade = int(request.form['quantidade'])
        except ValueError:
            flash("Quantidade inválida.", "danger")
            return redirect(url_for('retirar_stock'))
        
        try:
            cursor.execute("SELECT idproduto, quantidade FROM produtos WHERE nome = %s", (produto,))
            produto_existente = cursor.fetchone()
            
            if not produto_existente:
                flash("Produto não encontrado no stock.", "danger")
                return redirect(url_for('retirar_stock'))
            
            idproduto = produto_existente['idproduto']
            quantidade_atual = produto_existente['quantidade']
            
            if quantidade > quantidade_atual:
                flash("Stock insuficiente para retirar essa quantidade.", "danger")
                return redirect(url_for('retirar_stock'))
            
            cursor.execute("""
                INSERT INTO stock (idproduto, produto, quantidade, acao, idutilizador)
                VALUES (%s, %s, %s, 'retirado', %s)
            """, (idproduto, produto, quantidade, session['user_id']))
            
            # Atualiza o stock na tabela produtos, subtraindo a quantidade retirada
            novo_valor = quantidade_atual - quantidade
            cursor.execute("UPDATE produtos SET quantidade = %s WHERE idproduto = %s", (novo_valor, idproduto))
            
            con.commit()
            flash("Stock retirado com sucesso!", "success")
        except Exception as e:
            con.rollback()
            flash(f"Erro ao retirar stock: {e}", "danger")
        finally:
            cursor.close()
            con.close()
        
        return redirect(url_for('stock'))
    
    else:  
        try:
            cursor.execute("SELECT * FROM produtos")
            produtos = cursor.fetchall()
        except Exception as e:
            flash(f"Erro ao carregar os produtos: {e}", "danger")
            produtos = []
        finally:
            cursor.close()
            con.close()
        
        return render_template('retirar_stock.html', produtos=produtos)
    
# Rota para criar um relatório financeiro do mes selecionado
@app.route('/exportar_pdf/<int:mes>', methods=['GET'])
@login_required
def exportar_pdf(mes):
    user_id = session['user_id']
    
    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    
    nome_mes = meses_nomes.get(mes, "Desconhecido")
    
    con = conectar_bd()
    cursor = con.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            r.valor,
            r.moeda AS simbolo_moeda
        FROM rendimentos r
        WHERE r.idutilizador = %s AND r.mes = %s
    """, (user_id, mes))
    rendimentos = cursor.fetchall()

    cursor.execute("""
        SELECT 
            c.nome_categoria,
            d.valor,
            d.moeda AS simbolo_moeda
        FROM despesas d
        JOIN categorias c ON d.idcategoria = c.idcategoria
        WHERE d.idutilizador = %s AND d.mes = %s
    """, (user_id, mes))
    despesas = cursor.fetchall()
    
    con.close()
    
    # Criar um PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Criação so cabeçalho
    try:
        logo_path = os.path.join(current_app.root_path, '')
        c.drawImage(logo_path, 50, 720, width=120, height=60)
    except:
        pass
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(300, 750, f"Relatório Financeiro - {nome_mes}")
    c.line(50, 710, 550, 710)
    
    #  Moeda(s)
    dados = [["Tipo", "Categoria", "Valor", "Moeda"]]
    
    for rendimento in rendimentos:
        dados.append([
            "Rendimento",
            "-",
            f"{rendimento['valor']:.2f}",
            rendimento.get('simbolo_moeda', '€')
        ])
    
    for despesa in despesas:
        dados.append([
            "Despesa",
            despesa['nome_categoria'],
            f"{despesa['valor']:.2f}",
            despesa.get('simbolo_moeda', '€')
        ])
    
    tabela = Table(dados, colWidths=[100, 150, 100, 50])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    
    tabela.wrapOn(c, 400, 600)
    tabela.drawOn(c, 50, 550)
    
    c.showPage()
    c.save()
    
    pdf = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=relatorio_{nome_mes}.pdf'
    
    return response