from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)
CORS(app)

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://ollama:11434')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://chatuser:chatpass@postgres:5432/chatdb')
MODEL_NAME = 'llama2'

# Configuration de la base de données
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Modèle de données pour les conversations
class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Modèle de données pour les messages
class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer)
    role = Column(String(20))  # 'user' ou 'assistant'
    content = Column(Text)
    model = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

# Créer les tables au démarrage
Base.metadata.create_all(engine)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Récupérer toutes les conversations"""
    try:
        session = Session()
        conversations = session.query(Conversation).order_by(Conversation.updated_at.desc()).all()
        
        result = [{
            'id': conv.id,
            'title': conv.title,
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat()
        } for conv in conversations]
        
        session.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Créer une nouvelle conversation"""
    try:
        data = request.json
        title = data.get('title', f'Conversation du {datetime.now().strftime("%d/%m/%Y %H:%M")}')
        
        session = Session()
        conversation = Conversation(title=title)
        session.add(conversation)
        session.commit()
        
        result = {
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat()
        }
        
        session.close()
        return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Récupérer une conversation avec tous ses messages"""
    try:
        session = Session()
        conversation = session.query(Conversation).filter_by(id=conversation_id).first()
        
        if not conversation:
            return jsonify({'error': 'Conversation non trouvée'}), 404
        
        messages = session.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()
        
        result = {
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat(),
            'messages': [{
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'model': msg.model,
                'created_at': msg.created_at.isoformat()
            } for msg in messages]
        }
        
        session.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Supprimer une conversation et tous ses messages"""
    try:
        session = Session()
        
        # Supprimer les messages
        session.query(Message).filter_by(conversation_id=conversation_id).delete()
        
        # Supprimer la conversation
        conversation = session.query(Conversation).filter_by(id=conversation_id).first()
        if conversation:
            session.delete(conversation)
            session.commit()
            session.close()
            return jsonify({'message': 'Conversation supprimée'}), 200
        else:
            session.close()
            return jsonify({'error': 'Conversation non trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Envoyer un message et sauvegarder dans la base de données"""
    try:
        data = request.json
        user_message = data.get('message', '')
        conversation_id = data.get('conversation_id')
        
        if not user_message:
            return jsonify({'error': 'Message requis'}), 400
        
        session = Session()
        
        # Créer une nouvelle conversation si nécessaire
        if not conversation_id:
            first_words = ' '.join(user_message.split()[:5])
            conversation = Conversation(title=first_words + '...')
            session.add(conversation)
            session.commit()
            conversation_id = conversation.id
        else:
            # Mettre à jour le timestamp de la conversation
            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation:
                conversation.updated_at = datetime.utcnow()
        
        # Sauvegarder le message de l'utilisateur
        user_msg = Message(
            conversation_id=conversation_id,
            role='user',
            content=user_message,
            model=MODEL_NAME
        )
        session.add(user_msg)
        session.commit()
        
        # Appel à l'API Ollama
        response = requests.post(
            f'{OLLAMA_HOST}/api/generate',
            json={
                'model': MODEL_NAME,
                'prompt': user_message,
                'stream': False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('response', '')
            
            # Sauvegarder la réponse de l'assistant
            assistant_msg = Message(
                conversation_id=conversation_id,
                role='assistant',
                content=ai_response,
                model=MODEL_NAME
            )
            session.add(assistant_msg)
            session.commit()
            
            session.close()
            
            return jsonify({
                'response': ai_response,
                'model': MODEL_NAME,
                'conversation_id': conversation_id
            })
        else:
            session.close()
            return jsonify({'error': 'Erreur du modèle IA'}), 500
            
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Erreur de connexion: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    """Récupérer la liste des modèles disponibles"""
    try:
        response = requests.get(f'{OLLAMA_HOST}/api/tags')
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({'error': 'Impossible de récupérer les modèles'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)