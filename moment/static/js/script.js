class MomentApp {
    constructor() {
        this.currentPage = 1;
        this.isLoading = false;
        this.hasMore = true;
        this.init();
    }
    
    init() {
        this.momentsContainer = document.getElementById('moments-container');
        this.loadMoreBtn = document.getElementById('load-more');
        this.loadingIndicator = document.getElementById('loading');
        this.modal = document.getElementById('image-modal');
        this.modalImage = document.getElementById('modal-image');
        this.modalVideo = document.getElementById('modal-video');
        this.closeModalBtn = document.getElementById('close-modal');
        
        this.setupModal();
        this.loadMoments();
        
        this.loadMoreBtn.addEventListener('click', () => {
            if (!this.isLoading && this.hasMore) {
                this.currentPage++;
                this.loadMoments();
            }
        });
        
        window.addEventListener('scroll', this.handleScroll.bind(this));
    }
    
    setupModal() {
        this.closeModalBtn.addEventListener('click', () => this.closeModal());
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.closeModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });
    }
    
    openModal(src, isVideo = false) {
        if (isVideo) {
            this.modalVideo.src = src;
            this.modalVideo.classList.remove('hidden');
            this.modalImage.classList.add('hidden');
        } else {
            this.modalImage.src = src;
            this.modalImage.classList.remove('hidden');
            this.modalVideo.classList.add('hidden');
        }
        this.modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
    
    closeModal() {
        this.modal.classList.add('hidden');
        document.body.style.overflow = 'auto';
        this.modalVideo.src = '';
    }
    
    async loadMoments() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();
        
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const key = urlParams.get('key') || window.templateVars?.key || '';
            const response = await fetch(`/api/moments/data?key=${encodeURIComponent(key)}&page=${this.currentPage}`);
            
            if (response.status === 401 || response.status === 400) {
                window.location.href = '/moments/login';
                return;
            }
            
            const data = await response.json();
            
            if (data.ok) {
                if (data.moments && data.moments.length > 0) {
                    this.renderMoments(data.moments);
                    this.hasMore = data.hasMore;
                    this.updateLoadMoreButton();
                } else {
                    if (this.currentPage === 1) {
                        this.showNoMoments();
                    }
                    this.hasMore = false;
                    this.updateLoadMoreButton();
                }
            } else {
                this.showError(data.error || '加载失败');
            }
        } catch (error) {
            console.error('加载失败:', error);
            this.showError('网络错误，请稍后重试');
        } finally {
            this.hideLoading();
            this.isLoading = false;
        }
    }
    
    renderMoments(moments) {
        moments.forEach(moment => {
            const momentElement = this.createMomentElement(moment);
            this.momentsContainer.appendChild(momentElement);
        });
    }
    
    createMomentElement(moment) {
        const element = document.createElement('div');
        element.className = 'bg-white rounded-xl shadow-lg hover-lift p-6 fade-in-up';
        element.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <div>
                    <div class="text-gradient font-bold text-lg">${this.escapeHtml(moment.nickname || '未知用户')}</div>
                    <div class="text-gray-500 text-sm">${this.formatTime(moment.time || '')}</div>
                </div>
            </div>
            
            <div class="text-gray-700 mb-4 leading-relaxed bg-gray-50 rounded-lg p-4 border-l-4 border-primary">
                ${this.escapeHtml(moment.content || '')}
            </div>
            
            ${this.renderMedia(moment.images || [], moment.videos || [])}
            
            <div class="flex justify-between items-center mt-4 pt-4 border-t border-gray-100">
                <div class="flex items-center space-x-4">
                    <div class="flex items-center text-gray-600">
                        <svg class="w-5 h-5 mr-1 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"></path>
                        </svg>
                        <span>${moment.like_count || 0}</span>
                    </div>
                    <div class="flex items-center text-gray-600">
                        <svg class="w-5 h-5 mr-1 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M18 5v8a2 2 0 01-2 2h-5l-5 4v-4H4a2 2 0 01-2-2V5a2 2 0 012-2h12a2 2 0 012 2zM7 8H5v2h2V8zm2 0h2v2H9V8zm6 0h-2v2h2V8z" clip-rule="evenodd"></path>
                        </svg>
                        <span>${moment.comment_count || 0}</span>
                    </div>
                </div>
            </div>
            
            ${this.renderComments(moment.comments || [])}
        `;
        
        this.attachMediaClickEvents(element);
        return element;
    }
    
    renderMedia(images, videos) {
        let mediaHtml = '';
        
        if (videos && videos.length > 0) {
            videos.forEach(url => {
                mediaHtml += `
                    <div class="video-container mb-4 rounded-lg overflow-hidden">
                        <video class="w-full h-auto" controls preload="metadata">
                            <source src="${url}" type="video/mp4">
                            您的浏览器不支持视频播放
                        </video>
                    </div>
                `;
            });
        } else if (images && images.length > 0) {
            let gridClass = 'image-grid-1';
            if (images.length === 2) gridClass = 'image-grid-2';
            else if (images.length === 3) gridClass = 'image-grid-3';
            else if (images.length >= 4) gridClass = 'image-grid-4';
            
            mediaHtml += `<div class="image-grid ${gridClass} mb-4">`;
            images.forEach(url => {
                mediaHtml += `
                    <div class="image-item cursor-pointer">
                        <img src="${url}" alt="动态图片" loading="lazy" class="hover:scale-105 transition-transform duration-300">
                    </div>
                `;
            });
            mediaHtml += '</div>';
        }
        
        return mediaHtml;
    }
    
    attachMediaClickEvents(element) {
        const images = element.querySelectorAll('.image-item img');
        images.forEach(img => {
            img.addEventListener('click', () => {
                this.openModal(img.src, false);
            });
        });
        
        const videos = element.querySelectorAll('.video-container');
        videos.forEach(container => {
            const video = container.querySelector('video');
            container.addEventListener('click', (e) => {
                if (!e.target.closest('button') && !e.target.closest('input')) {
                    this.openModal(video.src, true);
                }
            });
        });
    }
    
    renderComments(comments) {
        if (!comments || comments.length === 0) return '';
        
        let commentsHtml = '<div class="mt-4 space-y-3">';
        comments.forEach(comment => {
            commentsHtml += `
                <div class="comment-bubble rounded-lg p-3 fade-in-up">
                    <div class="flex justify-between items-center mb-2">
                        <div class="font-semibold text-primary">${this.escapeHtml(comment.watchName || '未知用户')}</div>
                        <div class="text-gray-400 text-sm">${this.formatTime(comment.createTime || '')}</div>
                    </div>
                    <div class="text-gray-700">${this.escapeHtml(comment.comment || '')}</div>
                </div>
            `;
        });
        commentsHtml += '</div>';
        return commentsHtml;
    }
    
    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`;
        
        return date.toLocaleDateString('zh-CN');
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showLoading() {
        this.loadingIndicator.classList.remove('hidden');
        this.loadMoreBtn.classList.add('hidden');
    }
    
    hideLoading() {
        this.loadingIndicator.classList.add('hidden');
        this.loadMoreBtn.classList.remove('hidden');
    }
    
    updateLoadMoreButton() {
        if (!this.hasMore) {
            this.loadMoreBtn.classList.add('hidden');
        } else {
            this.loadMoreBtn.classList.remove('hidden');
        }
    }
    
    showError(message) {
        this.momentsContainer.innerHTML = `
            <div class="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
                <div class="text-red-600 font-semibold mb-2">加载失败</div>
                <div class="text-red-500 mb-4">${message}</div>
                <button onclick="location.reload()" class="bg-gradient-to-r from-primary to-secondary text-white px-6 py-2 rounded-full font-semibold hover:shadow-lg transition-all">
                    重新加载
                </button>
            </div>
        `;
    }
    
    showNoMoments() {
        this.momentsContainer.innerHTML = `
            <div class="text-center py-12">
                <div class="text-6xl mb-4">🎯</div>
                <div class="text-gray-600 text-lg">暂无动态，快去发布第一条动态吧！</div>
            </div>
        `;
    }
    
    handleScroll() {
        if (this.isLoading || !this.hasMore) return;
        
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        
        if (scrollTop + windowHeight >= documentHeight - 100) {
            if (!this.isLoading && this.hasMore) {
                this.currentPage++;
                this.loadMoments();
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const key = urlParams.get('key') || window.templateVars?.key || '';
    
    if (!key) {
        window.location.href = '/moments/login';
    }
    
    document.getElementById('logout-btn').addEventListener('click', function() {
        window.location.href = '/moments/login';
    });
    
    new MomentApp();
});