// 监督模式控制器
class SupervisorController {
    constructor(globalState) {
        this.globalState = globalState;
        this.radarChart = null;
        this.isInitialized = false;
        
        // 绑定状态监听
        this.globalState.addListener((type, newValue, oldValue, state) => {
            this.handleStateChange(type, newValue, oldValue, state);
        });
    }

    // 初始化监督模式界面
    initialize() {
        if (this.isInitialized) return;
        
        this.createSupervisorInterface();
        this.initializeRadarChart();
        this.bindEvents();
        this.updateDisplay();
        
        this.isInitialized = true;
        console.log('监督模式已初始化');
    }

    // 创建监督模式界面
    createSupervisorInterface() {
        const supervisorInterface = document.getElementById('supervisor-interface');
        if (!supervisorInterface) return;

        supervisorInterface.innerHTML = `
            <div class="supervisor-container">
                <div class="supervisor-left">
                    <div class="radar-section">
                        <h3>伍力属性雷达图</h3>
                        <div class="radar-container">
                            <canvas id="radar-chart" width="300" height="300"></canvas>
                        </div>
                    </div>
                    
                    <div class="history-section">
                        <h3>操作历史</h3>
                        <div id="supervisor-history" class="history-list"></div>
                    </div>
                </div>
                
                <div class="supervisor-right">
                    <div class="attributes-section">
                        <h3>伍力控制面板</h3>
                        <div class="attributes-controls">
                            ${Object.entries(this.globalState.getAttributes()).map(([attr, value]) => `
                                <div class="attribute-control">
                                    <label>${attr}</label>
                                    <div class="control-group">
                                        <button class="attr-btn minus" data-attr="${attr}">-</button>
                                        <input type="number" class="attr-input" data-attr="${attr}" 
                                               value="3" min="0" max="10">
                                        <button class="attr-btn plus" data-attr="${attr}">+</button>
                                    </div>
                                    <div class="attr-value">3</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    <div class="game-info-section">
                        <h3>游戏状态</h3>
                        <div class="game-info">
                            <div class="info-item">
                                <span>游戏状态:</span>
                                <span id="supervisor-game-status">未开始</span>
                            </div>
                            <div class="info-item">
                                <span>当前阶段:</span>
                                <span id="supervisor-current-phase">启蒙期</span>
                            </div>
                            <div class="info-item">
                                <span>剩余时间:</span>
                                <span id="supervisor-remaining-time">83:20</span>
                            </div>
                            <div class="info-item">
                                <span>已完成卡牌:</span>
                                <span id="supervisor-cards-completed">0</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="supervisor-actions">
                        <button id="reset-attributes" class="action-btn">重置属性</button>
                        <button id="export-data" class="action-btn">导出数据</button>
                    </div>
                </div>
            </div>
        `;
    }

    // 初始化雷达图
    initializeRadarChart() {
        const canvas = document.getElementById('radar-chart');
        if (!canvas) return;

        this.radarChart = new RadarChart(canvas, this.globalState.getAttributes());
    }

    // 绑定事件
    bindEvents() {
        // 属性控制按钮
        document.querySelectorAll('.attr-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const attr = e.target.dataset.attr;
                const isPlus = e.target.classList.contains('plus');
                this.adjustAttribute(attr, isPlus ? 1 : -1);
            });
        });

        // 属性输入框
        document.querySelectorAll('.attr-input').forEach(input => {
            input.addEventListener('change', (e) => {
                const attr = e.target.dataset.attr;
                const value = parseInt(e.target.value);
                if (!isNaN(value)) {
                    this.setAttributeValue(attr, value);
                }
            });
        });

        // 重置属性按钮
        const resetBtn = document.getElementById('reset-attributes');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetAttributes());
        }

        // 导出数据按钮
        const exportBtn = document.getElementById('export-data');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }
    }

    // 调整属性值
    adjustAttribute(attr, change) {
        const currentValue = this.globalState.getAttributes()[attr];
        const newValue = Math.max(0, Math.min(10, currentValue + change));
        this.globalState.updateAttribute(attr, newValue);
    }

    // 设置属性值
    setAttributeValue(attr, value) {
        const clampedValue = Math.max(0, Math.min(10, value));
        this.globalState.updateAttribute(attr, clampedValue);
    }

    // 重置所有属性
    resetAttributes() {
        const resetValues = {
            'R·安全力': 3, 'A·脑波力': 3, 'S·实感力': 3, 'P·创心力': 3, 'E·沟通力': 3
        };
        this.globalState.setAttributes(resetValues);
    }

    // 处理状态变化
    handleStateChange(type, newValue, oldValue, state) {
        switch (type) {
            case 'attributes':
            case 'attribute':
                this.updateAttributesDisplay();
                this.updateRadarChart();
                break;
            case 'gameStatus':
                this.updateGameStatus();
                break;
            case 'remainingTime':
                this.updateRemainingTime();
                break;
            case 'historyAdded':
                this.updateHistory();
                this.updateGameInfo();
                break;
        }
    }

    // 更新属性显示
    updateAttributesDisplay() {
        const attributes = this.globalState.getAttributes();
        
        Object.entries(attributes).forEach(([attr, value]) => {
            const input = document.querySelector(`.attr-input[data-attr="${attr}"]`);
            const valueDisplay = input?.parentElement.nextElementSibling;
            
            if (input) input.value = value;
            if (valueDisplay) valueDisplay.textContent = value;
        });
    }

    // 更新雷达图
    updateRadarChart() {
        if (this.radarChart) {
            this.radarChart.updateData(this.globalState.getAttributes());
        }
    }

    // 更新游戏状态显示
    updateGameStatus() {
        const statusElement = document.getElementById('supervisor-game-status');
        if (statusElement) {
            const statusMap = {
                'stopped': '未开始',
                'playing': '进行中',
                'paused': '已暂停'
            };
            statusElement.textContent = statusMap[this.globalState.state.gameStatus] || '未知';
        }
    }

    // 更新剩余时间显示
    updateRemainingTime() {
        const timeElement = document.getElementById('supervisor-remaining-time');
        if (timeElement) {
            const time = this.globalState.state.remainingTime;
            const minutes = Math.floor(time / 60);
            const seconds = time % 60;
            timeElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
    }

    // 更新历史记录显示
    updateHistory() {
        const historyElement = document.getElementById('supervisor-history');
        if (!historyElement) return;

        const history = this.globalState.state.gameHistory.slice(-10); // 显示最近10条
        historyElement.innerHTML = history.map(entry => {
            const changes = entry.optionData ? 
                Object.entries(entry.optionData.attributeEffects)
                    .filter(([k,v]) => v !== 0)
                    .map(([k,v]) => `${k}${v>0?'+':''}${v}`)
                    .join(', ') || '无变化' : '无变化';
            
            return `
                <div class="history-item">
                    <div class="history-time">${new Date(entry.timestamp).toLocaleTimeString()}</div>
                    <div class="history-content">
                        <div>卡牌${entry.cardId} - 选项${entry.selectedOption}</div>
                        <div class="history-event">${entry.cardData ? entry.cardData.safetyType : ''}</div>
                        <div class="history-changes">${changes}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // 更新游戏信息
    updateGameInfo() {
        const phaseElement = document.getElementById('supervisor-current-phase');
        const completedElement = document.getElementById('supervisor-cards-completed');
        
        if (phaseElement) phaseElement.textContent = this.globalState.state.currentPhase;
        if (completedElement) completedElement.textContent = this.globalState.state.cardsCompleted;
    }
    
    // 更新所有显示
    updateDisplay() {
        this.updateAttributesDisplay();
        this.updateRadarChart();
        this.updateGameStatus();
        this.updateRemainingTime();
        this.updateHistory();
        this.updateGameInfo();
    }

    // 导出数据
    exportData() {
        const data = {
            timestamp: new Date().toISOString(),
            gameState: this.globalState.getState(),
            snapshot: this.globalState.getSnapshot()
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `supervisor-data-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// 简单的雷达图实现
class RadarChart {
    constructor(canvas, data) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.data = data;
        this.center = { x: canvas.width / 2, y: canvas.height / 2 };
        this.radius = Math.min(canvas.width, canvas.height) / 2 - 40;
        
        this.draw();
    }

    updateData(newData) {
        this.data = newData;
        this.draw();
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        const attributes = Object.keys(this.data);
        const values = Object.values(this.data);
        const angleStep = (2 * Math.PI) / attributes.length;

        // 绘制网格
        this.drawGrid(attributes, angleStep);
        
        // 绘制数据
        this.drawData(values, angleStep);
        
        // 绘制标签
        this.drawLabels(attributes, angleStep);
        
        // 绘制总分值
        this.drawTotalScore(values);
    }

    drawGrid(attributes, angleStep) {
        this.ctx.strokeStyle = '#e0e0e0';
        this.ctx.lineWidth = 1;

        // 绘制同心圆
        for (let i = 1; i <= 5; i++) {
            this.ctx.beginPath();
            this.ctx.arc(this.center.x, this.center.y, (this.radius * i) / 5, 0, 2 * Math.PI);
            this.ctx.stroke();
        }

        // 绘制射线
        for (let i = 0; i < attributes.length; i++) {
            const angle = i * angleStep - Math.PI / 2;
            const x = this.center.x + Math.cos(angle) * this.radius;
            const y = this.center.y + Math.sin(angle) * this.radius;
            
            this.ctx.beginPath();
            this.ctx.moveTo(this.center.x, this.center.y);
            this.ctx.lineTo(x, y);
            this.ctx.stroke();
        }
    }

    drawData(values, angleStep) {
        this.ctx.fillStyle = 'rgba(102, 126, 234, 0.3)';
        this.ctx.strokeStyle = '#667eea';
        this.ctx.lineWidth = 2;

        this.ctx.beginPath();
        for (let i = 0; i < values.length; i++) {
            const angle = i * angleStep - Math.PI / 2;
            const value = values[i] / 10; // 归一化到0-1
            const x = this.center.x + Math.cos(angle) * this.radius * value;
            const y = this.center.y + Math.sin(angle) * this.radius * value;
            
            if (i === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        }
        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.stroke();

        // 绘制数据点
        this.ctx.fillStyle = '#667eea';
        for (let i = 0; i < values.length; i++) {
            const angle = i * angleStep - Math.PI / 2;
            const value = values[i] / 10;
            const x = this.center.x + Math.cos(angle) * this.radius * value;
            const y = this.center.y + Math.sin(angle) * this.radius * value;
            
            this.ctx.beginPath();
            this.ctx.arc(x, y, 4, 0, 2 * Math.PI);
            this.ctx.fill();
        }
    }

    drawLabels(attributes, angleStep) {
        this.ctx.fillStyle = '#333';
        this.ctx.font = '12px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';

        for (let i = 0; i < attributes.length; i++) {
            const angle = i * angleStep - Math.PI / 2;
            const x = this.center.x + Math.cos(angle) * (this.radius + 20);
            const y = this.center.y + Math.sin(angle) * (this.radius + 20);
            
            this.ctx.fillText(attributes[i], x, y);
        }
    }

    drawTotalScore(values) {
        // 计算总分
        const totalScore = values.reduce((sum, value) => sum + value, 0);
        const maxScore = values.length * 10; // 最大可能分数
        
        // 绘制总分数字
        this.ctx.fillStyle = '#667eea';
        this.ctx.font = 'bold 20px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(totalScore.toString(), this.center.x, this.center.y - 8);
        
        // 绘制"总分"标签
        this.ctx.fillStyle = '#666';
        this.ctx.font = '12px Arial';
        this.ctx.fillText('总分', this.center.x, this.center.y + 8);
        
        // 绘制分数比例
        this.ctx.fillStyle = '#999';
        this.ctx.font = '10px Arial';
        this.ctx.fillText(`/ ${maxScore}`, this.center.x, this.center.y + 20);
    }
}

// 导出
if (typeof window !== 'undefined') {
    window.SupervisorController = SupervisorController;
    window.RadarChart = RadarChart;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SupervisorController, RadarChart };
}