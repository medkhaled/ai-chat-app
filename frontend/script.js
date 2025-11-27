const API_URL = 'http://localhost:5000';
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const conversationsList = document.getElementById('conversationsList');
const deleteBtn = document.getElementById('deleteBtn');

let currentConversationId = null;

// Auto-resize textarea
messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});

// Envoyer avec Entrée
messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Charger les conversations au démarrage
async function loadConversations() {
    try {
        const response = await fetch(`${API_URL}/api/conversations`);
        const conversations = await response.json();
        
        conversationsList.innerHTML = '';
        
        if (conversations.length === 0) {
            conversationsList.innerHTML = '<p style="color: #888; padding: 20px; text-align: center;">Aucune conversation</p>';
            return;
        }
        
        conversations.forEach(conv => {
            const div = document.createElement('div');
            div.className = 'conversation-item';
            if (conv.id === currentConversationId) {
                div.classList.add('active');
            }
            
            const date = new Date(conv.updated_at);
            const formattedDate = date.toLocaleDateString('fr-FR') + ' ' + date.toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'});
            
            div.innerHTML = `
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-date">${formattedDate}</div>
            `;
            
            div.onclick = () => loadConversation(conv.id);
            conversationsList.appendChild(div);
        });
    } catch (error) {
        console.error('Erreur lors du chargement des conversations:', error);
    }
}

// Charger une conversation spécifique
async function loadConversation(conversationId) {
    try {
        const response = await fetch(`${API_URL}/api/conversations/${conversationId}`);
        const conversation = await response.json();
        
        currentConversationId = conversationId;
        chatContainer.innerHTML = '';
        
        conversation.messages.forEach(msg => {
            addMessage(msg.content, msg.role === 'user');
        });
        
        // Mettre à jour l'interface
        loadConversations();
        deleteBtn.style.display = 'block';
        
    } catch (error) {
        console.error('Erreur lors du chargement de la conversation:', error);
    }
}

// Créer une nouvelle conversation
async function createNewConversation() {
    currentConversationId = null;
    chatContainer.innerHTML = `
        <div class="welcome-message">
            <h2>👋 Nouvelle conversation</h2>
            <p>Posez votre première question pour commencer !</p>
        </div>
    `;
    deleteBtn.style.display = 'none';
    messageInput.focus();
    
    // Retirer la sélection active
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
    });
}

// Supprimer la conversation actuelle
async function deleteCurrentConversation() {
    if (!currentConversationId) return;
    
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette conversation ?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/conversations/${currentConversationId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            createNewConversation();
            loadConversations();
        }
    } catch (error) {
        console.error('Erreur lors de la suppression:', error);
        alert('Erreur lors de la suppression de la conversation');
    }
}

function addMessage(content, isUser = false) {
    // Supprimer le message de bienvenue s'il existe
    const welcomeMsg = chatContainer.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<strong>${isUser ? 'Vous' : 'Assistant'} :</strong> ${content}`;
    
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    // Scroll vers le bas
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    return messageDiv;
}

function addLoadingMessage() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot-message';
    loadingDiv.id = 'loading-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = '<strong>Assistant :</strong> <span class="loading"></span><span class="loading"></span><span class="loading"></span>';
    
    loadingDiv.appendChild(contentDiv);
    chatContainer.appendChild(loadingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    return loadingDiv;
}

function removeLoadingMessage() {
    const loadingMsg = document.getElementById('loading-message');
    if (loadingMsg) {
        loadingMsg.remove();
    }
}

async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // Désactiver le bouton
    sendButton.disabled = true;
    
    // Ajouter le message de l'utilisateur
    addMessage(message, true);
    
    // Vider l'input
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // Ajouter le message de chargement
    addLoadingMessage();
    
    try {
        const response = await fetch(`${API_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                conversation_id: currentConversationId
            })
        });
        
        const data = await response.json();
        
        // Supprimer le message de chargement
        removeLoadingMessage();
        
        if (response.ok) {
            addMessage(data.response);
            
            // Mettre à jour l'ID de la conversation si c'est une nouvelle
            if (!currentConversationId) {
                currentConversationId = data.conversation_id;
                deleteBtn.style.display = 'block';
            }
            
            // Recharger la liste des conversations
            loadConversations();
        } else {
            addMessage(`❌ Erreur: ${data.error || 'Une erreur est survenue'}`, false);
        }
    } catch (error) {
        removeLoadingMessage();
        addMessage(`❌ Erreur de connexion: ${error.message}. Assurez-vous que le backend est démarré.`, false);
    } finally {
        sendButton.disabled = false;
        messageInput.focus();
    }
}

// Vérifier la santé du backend et charger les conversations au démarrage
async function init() {
    try {
        const response = await fetch(`${API_URL}/api/health`);
        if (response.ok) {
            loadConversations();
        } else {
            console.warn('Backend non disponible');
        }
    } catch (error) {
        console.warn('Impossible de contacter le backend:', error);
    }
}

init();