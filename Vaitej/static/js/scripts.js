/**
 * ====================================================================
 * VAITEJ VENTURES - MAIN DASHBOARD SCRIPT
 * ====================================================================
 * Handles:
 * 1. Real-time Messaging (Polling & AJAX)
 * 2. Interactive Charts (Chart.js)
 * 3. File Upload Previews
 * 4. UI Interactions (Tabs, Toggles)
 */

document.addEventListener("DOMContentLoaded", () => {
    initChatSystem();
    initTractionCharts();
    initFileUploaders();
});

/* ====================================================================
   1. REAL-TIME CHAT SYSTEM
   ==================================================================== */
function initChatSystem() {
    const chatContainer = document.getElementById("messagesList");
    const chatForm = document.getElementById("chatForm");
    const msgInput = document.getElementById("msgInput");

    // Exit if not on the chat page or no active conversation
    if (!chatContainer || !window.currentConversationId) return;

    const conversationId = window.currentConversationId;
    let lastMessageCount = 0;
    let isUserScrolling = false;

    // Detect if user is scrolling up (to prevent auto-scroll annoyance)
    chatContainer.addEventListener("scroll", () => {
        const scrollPos = chatContainer.scrollTop + chatContainer.clientHeight;
        const isNearBottom = chatContainer.scrollHeight - scrollPos < 100;
        isUserScrolling = !isNearBottom;
    });

    /**
     * Fetch messages from the server
     */
    async function fetchMessages() {
        try {
            const response = await fetch(`/api/chat/${conversationId}`);
            if (!response.ok) throw new Error("Network response was not ok");
            
            const data = await response.json();
            
            // Only re-render if there are new messages
            if (data.messages.length !== lastMessageCount) {
                renderMessages(data.messages);
                lastMessageCount = data.messages.length;
                
                // Scroll to bottom if user is not looking at history
                if (!isUserScrolling) scrollToBottom();
            }
        } catch (error) {
            console.error("Chat polling error:", error);
        }
    }

    /**
     * Render message bubbles into the container
     */
    function renderMessages(messages) {
        if (messages.length === 0) {
            chatContainer.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); margin-top: 2rem;">
                    <p>No messages yet. Start the conversation!</p>
                </div>`;
            return;
        }

        const html = messages.map(msg => {
            const rowClass = msg.is_me ? "message-row me" : "message-row them";
            const bubbleClass = msg.is_me ? "bubble me" : "bubble them";
            
            return `
                <div class="${rowClass}">
                    <div class="${bubbleClass}">
                        ${escapeHtml(msg.text)}
                        <div class="msg-time">${msg.time}</div>
                    </div>
                </div>
            `;
        }).join("");

        chatContainer.innerHTML = html;
    }

    /**
     * Send a new message
     */
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = msgInput.value.trim();
        if (!text) return;

        // Optimistic UI: Clear input immediately
        msgInput.value = "";
        msgInput.focus();

        try {
            const res = await fetch("/api/chat/send", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    message: text
                })
            });

            if (res.ok) {
                fetchMessages(); // Trigger immediate update
            } else {
                alert("Failed to send. Please try again.");
            }
        } catch (err) {
            console.error("Send error:", err);
        }
    });

    // Helpers
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize Polling (Every 3 seconds)
    fetchMessages();
    setInterval(fetchMessages, 3000);
}

/* ====================================================================
   2. INTERACTIVE CHARTS (Chart.js)
   ==================================================================== */
function initTractionCharts() {
    const ctx = document.getElementById('tractionChart');
    
    // Exit if not on Traction page or no data provided
    if (!ctx || !window.chartData) return;

    const { labels, revenue, expenses } = window.chartData;

    // Handle Empty Data State gracefully
    const hasData = labels.length > 0 && labels[0] !== "Start";
    
    if (!hasData) {
        // Render a placeholder empty chart
        renderChart(ctx, ["Jan", "Feb", "Mar"], [0, 0, 0], [0, 0, 0]);
        return;
    }

    renderChart(ctx, labels, revenue, expenses);
}

function renderChart(canvas, labels, revenueData, expenseData) {
    const ctx = canvas.getContext('2d');

    // Create Gradient Fills
    const gradientRev = ctx.createLinearGradient(0, 0, 0, 400);
    gradientRev.addColorStop(0, 'rgba(16, 185, 129, 0.2)'); // Emerald
    gradientRev.addColorStop(1, 'rgba(16, 185, 129, 0)');

    const gradientExp = ctx.createLinearGradient(0, 0, 0, 400);
    gradientExp.addColorStop(0, 'rgba(244, 63, 94, 0.15)'); // Rose
    gradientExp.addColorStop(1, 'rgba(244, 63, 94, 0)');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Revenue',
                    data: revenueData,
                    borderColor: '#10b981',
                    backgroundColor: gradientRev,
                    borderWidth: 3,
                    pointBackgroundColor: '#09090b', // Matches body bg
                    pointBorderColor: '#10b981',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    fill: true,
                    tension: 0.4 // Smooth curves
                },
                {
                    label: 'Expenses',
                    data: expenseData,
                    borderColor: '#f43f5e',
                    backgroundColor: gradientExp,
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: { color: '#a1a1aa', font: { family: 'Inter', size: 12 }, usePointStyle: true },
                    align: 'end'
                },
                tooltip: {
                    backgroundColor: 'rgba(24, 24, 27, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#a1a1aa',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    boxPadding: 4
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)', drawBorder: false },
                    ticks: { color: '#71717a', font: { family: 'Inter' } },
                    beginAtZero: true
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#71717a', font: { family: 'Inter' } }
                }
            }
        }
    });
}

/* ====================================================================
   3. FILE UPLOAD & UI INTERACTIONS
   ==================================================================== */
function initFileUploaders() {
    
    // A. Logo Upload Preview (Settings Page)
    const logoInput = document.getElementById('logo-input');
    if (logoInput) {
        logoInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const previewContainer = document.querySelector('.current-logo');
                    // Remove existing content (text or old img)
                    previewContainer.innerHTML = ''; 
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.objectFit = 'cover';
                    previewContainer.appendChild(img);
                }
                reader.readAsDataURL(file);
            }
        });
    }

    // B. Pitch Deck Filename Display
    const deckInput = document.getElementById('file-upload');
    if (deckInput) {
        const label = document.querySelector('label[for="file-upload"]');
        const originalText = label.innerText;

        deckInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                label.innerText = `📄 ${e.target.files[0].name}`;
                label.style.borderColor = '#10b981'; // Green border
                label.style.color = '#10b981';
            } else {
                label.innerText = originalText;
            }
        });
    }
}