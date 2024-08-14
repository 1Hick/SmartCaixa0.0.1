from datetime import datetime, date, timedelta
import io
from flask import Flask, jsonify, render_template, request, redirect, send_file, url_for, session
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from fpdf import FPDF
from models import FechamentoCaixa, Transacao, db, Usuario, Categoria, Produto, ItemTransacao


from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smartcaixa.db'
app.config['SECRET_KEY'] = 'Ayce'
app.config['UPLOAD_FOLDER'] = 'static/imagens'
db.init_app(app)

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

migrate = Migrate(app, db)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('pdv'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('pdv'))

    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        user = Usuario.query.filter_by(usuario=usuario).first()
        if user and check_password_hash(user.senha, senha):
            login_user(user)
            session['usuario'] = usuario
            session['abertura'] = datetime.now().isoformat()  # Armazenar a hora de abertura
            session['fechamento_realizado'] = False  # Inicialmente, o fechamento não foi realizado
            return redirect(url_for('pdv'))
        return 'Usuário ou senha inválidos', 401

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('usuario', None)
    session.pop('fechamento_realizado', None)  # Remover a flag de fechamento
    return redirect(url_for('index'))


@app.route('/pdv')
@login_required
def pdv():
    if 'fechamento_realizado' in session and session['fechamento_realizado']:
        # Se o fechamento foi realizado, redireciona para a tela de login
        return redirect(url_for('logout'))
    
    # Se o fechamento não foi realizado, permite o acesso ao PDV
    return render_template('pdv.html')




@app.route('/finalizar_compra', methods=['POST'])
def finalizar_compra():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    dados = request.get_json()
    carrinho = dados.get('carrinho', [])
    pagamento = dados.get('pagamento')
    valor_recebido = dados.get('valor_recebido')
    imprimir_nota = dados.get('imprimir_nota', False)
    
    if not carrinho:
        return jsonify({'status': 'error', 'message': 'Carrinho vazio!'}), 400
    
    total = sum(item['preco'] * item['quantidade'] for item in carrinho)
    troco = valor_recebido - total

    if pagamento == 'dinheiro' and troco < 0:
        return jsonify({'status': 'error', 'message': 'Valor recebido insuficiente!'}), 400

    for item in carrinho:
        produto = Produto.query.get(item['id'])
        if produto:
            produto.estoque -= item['quantidade']
            if produto.estoque < 0:
                return jsonify({'status': 'error', 'message': f'Estoque insuficiente para {produto.nome}!'}), 400
            db.session.add(produto)
    
    nova_transacao = Transacao(
        data=datetime.now(),
        valor=total,
        metodo_pagamento=pagamento
    )
    db.session.add(nova_transacao)
    db.session.commit()
    
    for item in carrinho:
        item_transacao = ItemTransacao(
            produto_id=item['id'],
            quantidade=item['quantidade'],
            preco=item['preco'],
            transacao=nova_transacao
        )
        db.session.add(item_transacao)
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Compra finalizada com sucesso!'}), 200
    

@app.route('/categorias')
def categorias():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    categorias = Categoria.query.all()
    return render_template('categorias.html', categorias=categorias)

@app.route('/add_categoria', methods=['POST'])
def add_categoria():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    nome_categoria = request.form['nome_categoria']
    nova_categoria = Categoria(nome=nome_categoria)
    db.session.add(nova_categoria)
    db.session.commit()
    return redirect(url_for('categorias'))

@app.route('/produtos')
def produtos():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    produtos = Produto.query.all()
    categorias = Categoria.query.all()
    return render_template('produtos.html', produtos=produtos, categorias=categorias)

@app.route('/add_produto', methods=['POST'])
def add_produto():
    nome = request.form['nome_produto']
    descricao = request.form['descricao_produto']
    codigo_barras = request.form['codigo_barras']
    preco = float(request.form['preco_produto'])
    estoque = int(request.form['estoque_produto'])
    
    categoria_id = int(request.form['categoria_id'])
    
    # Processa imagem se houver
    imagem = None
    if 'imagem_produto' in request.files:
        imagem_file = request.files['imagem_produto']
        if imagem_file.filename != '':
            imagem = imagem_file.filename
            imagem_file.save(f'static/imagens/{imagem}')

    novo_produto = Produto(
        nome=nome,
        descricao=descricao,
        codigo_barras=codigo_barras,
        preco=preco,
        estoque=estoque,
        
        categoria_id=categoria_id,
        imagem=imagem
    )
    
    db.session.add(novo_produto)
    db.session.commit()
    
    return redirect(url_for('produtos'))

@app.route('/edit_produto/<int:produto_id>', methods=['POST'])
def edit_produto(produto_id):
    if 'usuario' not in session:
        return redirect(url_for('index'))
    
    produto = Produto.query.get_or_404(produto_id)
    
    # Obtendo valores do formulário e garantindo que não sejam None
    nome_produto = request.form.get('nome_produto')
    descricao_produto = request.form.get('descricao_produto')
    codigo_barras = request.form.get('codigo_barras')
    preco_produto = request.form.get('preco_produto')
    estoque_produto = request.form.get('estoque_produto')
    categoria_id = request.form.get('categoria_id')
    
    
    # Verificando se os valores não são vazios
    if nome_produto:
        produto.nome = nome_produto
    if descricao_produto:
        produto.descricao = descricao_produto
    if codigo_barras:
        produto.codigo_barras = codigo_barras
    if preco_produto:
        produto.preco = preco_produto
    if estoque_produto:
        produto.estoque = estoque_produto
    if categoria_id:
        produto.categoria_id = categoria_id
    
    imagem_produto = request.files.get('imagem_produto')
    if imagem_produto and imagem_produto.filename:
        imagem_filename = secure_filename(imagem_produto.filename)
        imagem_produto.save(os.path.join(app.config['UPLOAD_FOLDER'], imagem_filename))
        produto.imagem = imagem_filename

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Adicione um log ou um tratamento de erro aqui se necessário
        print(f"Erro ao atualizar o produto: {e}")
        return redirect(url_for('produtos', error="Erro ao atualizar o produto"))
    
    return redirect(url_for('produtos'))



@app.route('/transacoes', methods=['GET'])
def transacoes():
    filtro = request.args.get('filtro', 'hoje')
    pagina = int(request.args.get('page', 1))
    limite = 200  # Número de transações por página

    # Filtra transações com base no filtro (hoje, semana, mês)
    if filtro == 'hoje':
        transacoes_query = Transacao.query.filter(Transacao.data >= date.today())
    elif filtro == 'semana':
        start_date = date.today() - timedelta(days=date.today().weekday())
        transacoes_query = Transacao.query.filter(Transacao.data >= start_date)
    elif filtro == 'mes':
        start_date = date.today().replace(day=1)
        transacoes_query = Transacao.query.filter(Transacao.data >= start_date)
    else:
        transacoes_query = Transacao.query

    # Contar total de transações para paginação
    total_transacoes = transacoes_query.count()
    
    # Paginando os resultados
    transacoes_detalhadas = transacoes_query.paginate(page=pagina, per_page=limite)

    # Calculando o total dos valores
    total = sum(t.valor for t in transacoes_detalhadas.items)

    return render_template('transacoes.html', 
                           transacoes_detalhadas=transacoes_detalhadas.items, 
                           filtro=filtro,
                           pagina=pagina,
                           total_transacoes=total_transacoes,
                           limite=limite,
                           total=total)


@app.route('/fechamento', methods=['GET', 'POST'])
@login_required
def fechamento():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        abertura_str = session.get('abertura')  # Hora de abertura armazenada na sessão
        if not abertura_str:
            return "Hora de abertura não encontrada.", 400

        abertura = datetime.fromisoformat(abertura_str)
        fechamento = datetime.now()
        fundo_caixa = float(request.form.get('fundo_caixa', 0))
        usuario_id = Usuario.query.filter_by(usuario=session['usuario']).first().id

        # Cálculo do total por método de pagamento
        total_pix = db.session.query(db.func.sum(Transacao.valor)).filter(
            Transacao.metodo_pagamento == 'pix',
            Transacao.data >= abertura,
            Transacao.data <= fechamento
        ).scalar() or 0

        total_debito = db.session.query(db.func.sum(Transacao.valor)).filter(
            Transacao.metodo_pagamento == 'debito',
            Transacao.data >= abertura,
            Transacao.data <= fechamento
        ).scalar() or 0

        total_credito = db.session.query(db.func.sum(Transacao.valor)).filter(
            Transacao.metodo_pagamento == 'credito',
            Transacao.data >= abertura,
            Transacao.data <= fechamento
        ).scalar() or 0

        total_dinheiro = db.session.query(db.func.sum(Transacao.valor)).filter(
            Transacao.metodo_pagamento == 'dinheiro',
            Transacao.data >= abertura,
            Transacao.data <= fechamento
        ).scalar() or 0

        total_vendas = total_pix + total_debito + total_credito + total_dinheiro
        saldo_final = fundo_caixa + total_vendas

        fechamento = FechamentoCaixa(
            abertura=abertura,
            fechamento=fechamento,
            fundo_caixa=fundo_caixa,
            total_pix=total_pix,
            total_debito=total_debito,
            total_credito=total_credito,
            total_dinheiro=total_dinheiro,
            total_vendas=total_vendas,
            saldo_final=saldo_final,
            usuario_id=usuario_id
        )

        db.session.add(fechamento)
        db.session.commit()

        session['fechamento_realizado'] = True
        return render_template('fechamento.html', fechamento=fechamento)

    return render_template('fechamento.html')





@app.route('/configuracoes')
def configuracoes():
    if current_user.is_admin:
        usuarios = Usuario.query.all()
        return render_template('configuracoes.html', usuarios=usuarios)
    return redirect(url_for('pdv'))

@app.route('/add_usuario', methods=['POST'])
def add_usuario():
    usuario = request.form['usuario']
    senha = request.form['senha']
    nivel_acesso = request.form['nivel_acesso']
    
    senha_hash = generate_password_hash(senha)
    novo_usuario = Usuario(usuario=usuario, senha=senha_hash, nivel_acesso=nivel_acesso)
    db.session.add(novo_usuario)
    db.session.commit()
    
    return redirect(url_for('configuracoes'))

# Adicione uma rota para deletar um usuário
@app.route('/delete_usuario', methods=['POST'])
def delete_usuario():
    usuario_id = request.form['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    
    if usuario:
        db.session.delete(usuario)
        db.session.commit()
    
    return redirect(url_for('configuracoes'))



@app.route('/gerar_relatorio', methods=['POST'])
def gerar_relatorio():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    
    # Obtém todas as transações
    transacoes = Transacao.query.all()
    
    # Prepara o resumo das transações
    total = sum(t.valor for t in transacoes)
    
    resumo = [f"{t.data} - {t.valor} - {t.metodo_pagamento}" for t in transacoes]
    resumo.append(f"Total: {total}")
    # Gera o PDF e obtém o conteúdo em memória
    pdf_content = gerar_pdf(resumo)
    
    # Envia o PDF como resposta para download
    return send_file(
        pdf_content,
        as_attachment=True,
        download_name='relatorio_transacoes.pdf',
        mimetype='application/pdf'
    )


def gerar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for dado in dados:
        pdf.cell(200, 10, txt=dado, ln=True)

    # Salva o PDF em memória como string
    pdf_output = io.BytesIO()
    pdf_output.write(pdf.output(dest='S').encode('latin1'))  # 'S' para retornar como string
    pdf_output.seek(0)  # Volta para o início do buffer

    return pdf_output

@app.route('/search_produto', methods=['GET'])
def search_produto():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    query = request.args.get('query', '')
    produtos = Produto.query.filter(
        Produto.nome.ilike(f'%{query}%') | Produto.codigo_barras.ilike(f'%{query}%')
    ).all()
    produtos_list = [{'id': p.id, 'nome': p.nome, 'descricao': p.descricao, 'codigo_barras': p.codigo_barras, 'preco': p.preco, 'estoque': p.estoque} for p in produtos]
    return jsonify(produtos_list)







from flask import send_file
from fpdf import FPDF
import io

from flask import send_file
from fpdf import FPDF
import io

@app.route('/gerar_pdf_fechamento', methods=['POST'])
@login_required
def gerar_pdf_fechamento():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    dados = {
        'abertura': request.form.get('abertura'),
        'fechamento': request.form.get('fechamento'),
        'total_pix': request.form.get('total_pix'),
        'total_debito': request.form.get('total_debito'),
        'total_credito': request.form.get('total_credito'),
        'total_dinheiro': request.form.get('total_dinheiro'),
        'fundo_caixa': request.form.get('fundo_caixa'),
        'total_vendas': request.form.get('total_vendas'),
        'saldo_final': request.form.get('saldo_final')
    }

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Relatório de Fechamento de Caixa", ln=True, align='C')
    for key, value in dados.items():
        pdf.cell(200, 10, txt=f"{key.replace('_', ' ').title()}: R$ {value}", ln=True, align='L')

    # Criar um buffer em memória
    pdf_output = io.BytesIO()
    pdf_output.write(pdf.output(dest='S').encode('latin1'))  # 'S' para retornar como string
    pdf_output.seek(0)  # Voltar para o início do buffer

    # Enviar o PDF como resposta
    return send_file(
        pdf_output,
        as_attachment=True,
        download_name="relatorio_fechamento.pdf",
        mimetype="application/pdf"
    )

@app.route('/adicionar_observacao', methods=['POST'])
@login_required
def adicionar_observacao():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    observacao = request.form.get('observacoes')
    fechamento_id = request.form.get('fechamento_id')

    fechamento = FechamentoCaixa.query.get_or_404(fechamento_id)
    fechamento.observacoes = observacao

    db.session.commit()

    return redirect(url_for('fechamento'))
from app import app  

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=13400, debug=True)
