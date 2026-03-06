/**
 * Starfield / Tunnel Effect for Welcome Screen
 * 实现星空穿越/隧道特效
 */

class Starfield {
    constructor(canvasId, callback) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.callback = callback; // 动画结束后的回调

        this.stars = [];
        this.numStars = 800;
        this.speed = 2;
        this.maxSpeed = 50;
        this.acceleration = 0.5;
        this.isAccelerating = false;
        this.animationId = null;

        this.init();
    }

    init() {
        this.resize();
        window.addEventListener('resize', () => this.resize());

        // 初始化星星
        for (let i = 0; i < this.numStars; i++) {
            this.stars.push(this.createStar());
        }

        // 点击加速
        document.getElementById('welcome-screen').addEventListener('click', () => {
            this.accelerate();
        });

        // 触摸加速
        document.getElementById('welcome-screen').addEventListener('touchstart', () => {
            this.accelerate();
        });

        this.animate();
    }

    resize() {
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;
        this.centerX = this.width / 2;
        this.centerY = this.height / 2;
    }

    createStar() {
        return {
            x: (Math.random() - 0.5) * this.width * 2, // 扩大范围防止边缘空白
            y: (Math.random() - 0.5) * this.height * 2,
            z: Math.random() * this.width, // 深度
            pz: 0 // 上一帧的深度，用于绘制轨迹
        };
    }

    accelerate() {
        if (this.isAccelerating) return;
        this.isAccelerating = true;

        // 隐藏文字
        const titles = document.querySelectorAll('.welcome-title, .welcome-subtitle, .click-hint');
        titles.forEach(el => {
            el.style.transition = 'opacity 0.5s';
            el.style.opacity = '0';
        });
    }

    update() {
        // 加速逻辑
        if (this.isAccelerating) {
            this.speed += this.acceleration;
            if (this.speed > this.maxSpeed) {
                // 达到最大速度，淡出欢迎页
                if (this.callback) this.callback();
                // 继续运行一小会儿直到完全消失
                if (this.speed > this.maxSpeed + 20) {
                    cancelAnimationFrame(this.animationId);
                    return;
                }
            }
        }

        // 绘制逻辑
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.4)'; // 拖影效果
        this.ctx.fillRect(0, 0, this.width, this.height);

        this.ctx.fillStyle = '#fff';

        for (let i = 0; i < this.stars.length; i++) {
            const star = this.stars[i];

            // 保存上一帧位置
            star.pz = star.z;

            // 移动星星
            star.z -= this.speed;

            // 重置星星
            if (star.z <= 0) {
                star.x = (Math.random() - 0.5) * this.width * 2;
                star.y = (Math.random() - 0.5) * this.height * 2;
                star.z = this.width;
                star.pz = star.z;
            }

            // 投影计算
            const x = this.centerX + (star.x / star.z) * this.width;
            const y = this.centerY + (star.y / star.z) * this.height;

            // 只有当星星在屏幕内时才绘制
            // if (x >= 0 && x <= this.width && y >= 0 && y <= this.height) {
            const size = (1 - star.z / this.width) * 4;
            const px = this.centerX + (star.x / star.pz) * this.width;
            const py = this.centerY + (star.y / star.pz) * this.height;

            // 绘制线条（速度线）
            this.ctx.beginPath();
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(x, y);

            // 颜色基于速度：速度越快越蓝/紫
            const hue = this.isAccelerating ? 240 + Math.random() * 60 : 0;
            const sat = this.isAccelerating ? 100 : 0;
            const light = this.isAccelerating ? 80 : 100;

            this.ctx.strokeStyle = `hsl(${hue}, ${sat}%, ${light}%)`;
            this.ctx.lineWidth = size;
            this.ctx.stroke();

            // 绘制星星点
            /*
            this.ctx.beginPath();
            this.ctx.arc(x, y, size > 0 ? size : 0, 0, Math.PI * 2);
            this.ctx.fill();
            */
            // }
        }
    }

    animate() {
        this.update();
        this.animationId = requestAnimationFrame(() => this.animate());
    }
}

// 自动初始化
window.addEventListener('load', () => {
    const welcomeScreen = document.getElementById('welcome-screen');
    if (!welcomeScreen) return;

    // 检查是否需要跳过欢迎页 (从完善资料页返回时)
    if (sessionStorage.getItem('skip_intro') === 'true') {
        welcomeScreen.style.display = 'none';
        sessionStorage.removeItem('skip_intro'); //清除标记，下次刷新还会显示（或者保留取决于需求，这里先清除以免一直不显示）
        return;
    }

    // 初始化星空
    new Starfield('welcome-canvas', () => {
        // 动画结束回调
        welcomeScreen.style.opacity = '0';
        setTimeout(() => {
            welcomeScreen.style.display = 'none';
        }, 1500); // 等待 CSS transition 结束
    });
});
