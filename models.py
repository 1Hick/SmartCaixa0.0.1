from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Column, String

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    senha = db.Column(db.String(120), nullable=False)
    nivel_acesso = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)  # Adiciona o atributo is_admin

    def get_id(self):
        return str(self.id)
    # Métodos necessários do UserMixin já estão implementados, então não é necessário sobrescrevê-los.

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    produtos = db.relationship('Produto', backref='categoria', lazy=True)

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200))
    codigo_barras = db.Column(db.String(100), unique=True, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    estoque = db.Column(db.Integer, nullable=False)
    imagem = db.Column(db.String(100))
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)


    def atualizar_estoque(self, quantidade_vendida):
        if quantidade_vendida > self.estoque:
            raise ValueError("Quantidade vendida excede o estoque disponível.")
        self.estoque -= quantidade_vendida
        db.session.commit()

class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    metodo_pagamento = db.Column(db.String(20), nullable=False)
    itens = db.relationship('ItemTransacao', backref='transacao', lazy=True)

    def adicionar_itens(self, itens):
        for item in itens:
            item_transacao = ItemTransacao(
                produto_id=item['id'],
                quantidade=item['quantidade'],
                preco=item['preco'],
                transacao=self
            )
            db.session.add(item_transacao)
        db.session.commit()

class ItemTransacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    transacao_id = db.Column(db.Integer, db.ForeignKey('transacao.id'), nullable=False)
    
    produto = db.relationship('Produto', backref='itens_transacao')

class FechamentoCaixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    abertura = db.Column(db.DateTime, nullable=False)
    fechamento = db.Column(db.DateTime, nullable=False)
    fundo_caixa = db.Column(db.Float, nullable=False)
    total_pix = db.Column(db.Float, default=0.0)
    total_debito = db.Column(db.Float, default=0.0)
    total_credito = db.Column(db.Float, default=0.0)
    total_dinheiro = db.Column(db.Float, default=0.0)
    total_vendas = db.Column(db.Float, default=0.0)
    saldo_final = db.Column(db.Float, default=0.0)
    observacoes = db.Column(db.Text, default='')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario = db.relationship('Usuario', backref=db.backref('fechamentos', lazy=True))


class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.String(200), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)

    def __init__(self, nome, endereco, telefone):
        self.nome = nome
        self.endereco = endereco
        self.telefone = telefone

class Atividade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.Column(db.String(150))
    acao = db.Column(db.String(255))
