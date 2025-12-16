// 全局状态管理系统
class GlobalState {
    constructor() {
        this.state = {
            // 五力属性
            attributes: {
                安全力: 3, 脑波力: 3, 实感力: 3, 创心力: 3, 沟通力: 3
            },
            // 游戏状态
            gameStatus: 'stopped', // stopped, playing, paused
            currentPhase: '启蒙期',
            remainingTime: 5000,
            defaultTime: 5000, // 默认倒计时长度
            gameStarted: false,
            // 历史记录
            gameHistory: [],
            // 当前模式
            displayMode: 'tabletop', // tabletop, player, supervisor
            // 统计信息
            cardsCompleted: 0,
            stageFailures: 0
        };
        
        this.listeners = new Set();
        this.systems = {};
    }

    // 注册系统组件
    registerSystem(name, system) {
        this.systems[name] = system;
    }

    // 获取状态
    getState() {
        return { ...this.state };
    }

    // 获取属性
    getAttributes() {
        return { ...this.state.attributes };
    }

    // 设置属性
    setAttributes(attributes) {
        const oldAttributes = { ...this.state.attributes };
        this.state.attributes = { ...attributes };
        this.notifyListeners('attributes', this.state.attributes, oldAttributes);
    }

    // 更新单个属性
    updateAttribute(name, value) {
        if (this.state.attributes.hasOwnProperty(name)) {
            const oldValue = this.state.attributes[name];
            this.state.attributes[name] = Math.max(0, Math.min(10, value));
            this.notifyListeners('attribute', { name, value: this.state.attributes[name], oldValue });
        }
    }

    // 批量更新属性
    updateAttributes(changes) {
        const oldAttributes = { ...this.state.attributes };
        Object.entries(changes).forEach(([attr, change]) => {
            if (this.state.attributes.hasOwnProperty(attr)) {
                this.state.attributes[attr] = Math.max(0, Math.min(10, this.state.attributes[attr] + change));
            }
        });
        this.notifyListeners('attributes', this.state.attributes, oldAttributes);
    }

    // 设置游戏状态
    setGameStatus(status) {
        const oldStatus = this.state.gameStatus;
        this.state.gameStatus = status;
        this.notifyListeners('gameStatus', status, oldStatus);
    }

    // 设置剩余时间
    setRemainingTime(time) {
        const oldTime = this.state.remainingTime;
        this.state.remainingTime = time;
        this.notifyListeners('remainingTime', time, oldTime);
    }

    // 设置默认倒计时长度
    setDefaultTime(time) {
        const oldTime = this.state.defaultTime;
        this.state.defaultTime = time;
        this.state.remainingTime = time;
        this.notifyListeners('defaultTime', time, oldTime);
    }

    // 设置显示模式
    setDisplayMode(mode) {
        const oldMode = this.state.displayMode;
        this.state.displayMode = mode;
        this.notifyListeners('displayMode', mode, oldMode);
    }

    // 添加历史记录
    addHistoryEntry(entry) {
        this.state.gameHistory.push(entry);
        this.notifyListeners('historyAdded', entry);
    }

    // 清空历史记录
    clearHistory() {
        this.state.gameHistory = [];
        this.notifyListeners('historyCleared');
    }

    // 重置游戏状态
    resetGame() {
        const oldState = { ...this.state };
        this.state = {
            ...this.state,
            attributes: {
                安全力: 3, 脑波力: 3, 实感力: 3, 创心力: 3, 沟通力: 3
            },
            gameStatus: 'stopped',
            gameStarted: false,
            remainingTime: this.state.defaultTime || 5000,
            cardsCompleted: 0,
            stageFailures: 0
        };
        this.notifyListeners('gameReset', this.state, oldState);
    }

    // 开始新游戏
    startNewGame() {
        this.resetGame();
        this.state.gameStatus = 'playing';
        this.state.gameStarted = true;
        this.notifyListeners('gameStarted', this.state);
    }

    // 添加监听器
    addListener(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    // 通知监听器
    notifyListeners(type, newValue, oldValue) {
        this.listeners.forEach(listener => {
            try {
                listener(type, newValue, oldValue, this.state);
            } catch (error) {
                console.error('状态监听器错误:', error);
            }
        });
    }

    // 保存状态到持久化系统
    saveState() {
        if (this.systems.persistence) {
            return this.systems.persistence.save(this.getState());
        }
        return false;
    }

    // 从持久化系统加载状态
    loadState() {
        if (this.systems.persistence) {
            const savedState = this.systems.persistence.load();
            if (savedState) {
                this.state = { ...this.state, ...savedState };
                this.notifyListeners('stateLoaded', this.state);
                return true;
            }
        }
        return false;
    }

    // 获取状态快照（用于调试）
    getSnapshot() {
        return {
            timestamp: new Date().toISOString(),
            state: this.getState(),
            listeners: this.listeners.size,
            systems: Object.keys(this.systems)
        };
    }
}

// 创建全局状态实例
const globalState = new GlobalState();

// 导出
if (typeof window !== 'undefined') {
    window.GlobalState = GlobalState;
    window.globalState = globalState;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GlobalState, globalState };
}