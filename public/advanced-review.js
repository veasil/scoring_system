            // 生成完整复盘报告
            window.generateAdvancedReport = async () => {
                if (!window.gameReviewModule) {
                    document.getElementById('choice-display').innerHTML = '<p style="color: red;">复盘模块未加载，请刷新页面重试</p>';
                    return;
                }
                
                const gameHistory = window.globalState.state.gameHistory || [];
                if (gameHistory.length === 0) {
                    document.getElementById('choice-display').innerHTML = '<p>暂无游戏记录，请先完成一些卡牌</p>';
                    return;
                }
                
                // 调用新的复盘模块
                await window.gameReviewModule.generateFullReport(gameHistory, gameAnalytics);
            };