// ==================== 医疗知识助手前端 ====================

// API 基础路径
const API_BASE = '';

// ==================== 工具函数 ====================

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '请求失败');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function formatMarkdown(text) {
    // 简单的 Markdown 渲染
    if (!text) return '';
    
    return text
        // 标题
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        // 粗体
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // 斜体
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // 代码块
        .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
        // 行内代码
        .replace(/`(.*?)`/g, '<code>$1</code>')
        // 列表
        .replace(/^\- (.*$)/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        // 分隔线
        .replace(/^---$/gm, '<hr>')
        // 换行
        .replace(/\n/g, '<br>');
}

function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="loading"></div> 加载中...';
    }
}

function showResult(elementId, content, isMarkdown = true) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = isMarkdown ? formatMarkdown(content) : content;
    }
}

function showError(elementId, error) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `<div class="warning-box critical"><h4>❌ 错误</h4><p>${error}</p></div>`;
    }
}

// ==================== 面板切换 ====================

document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        // 更新按钮状态
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // 切换面板
        const panelId = btn.dataset.panel;
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        document.getElementById(`panel-${panelId}`).classList.add('active');
    });
});

// ==================== 智能对话 ====================

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const clearHistoryBtn = document.getElementById('clear-history-btn');
const usePatientContext = document.getElementById('use-patient-context');
const contextPatientId = document.getElementById('context-patient-id');

// 启用/禁用患者ID输入
usePatientContext.addEventListener('change', () => {
    contextPatientId.disabled = !usePatientContext.checked;
});

// 发送消息
async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;
    
    // 获取患者ID
    const patientId = usePatientContext.checked ? contextPatientId.value.trim() : null;
    
    // 显示用户消息
    appendMessage('user', message);
    chatInput.value = '';
    
    // 显示加载状态
    const loadingMsg = appendMessage('assistant', '<div class="loading"></div> 思考中...');
    
    try {
        const result = await apiCall('/api/chat', {
            method: 'POST',
            body: JSON.stringify({ message, patient_id: patientId })
        });
        
        // 移除加载消息
        loadingMsg.remove();
        
        if (result.success && result.data) {
            let content = result.data.answer || result.data;
            
            // 添加来源信息
            if (result.data.sources && result.data.sources.length > 0) {
                content += '\n\n---\n**数据来源:** ';
                const sources = result.data.sources.map(s => {
                    if (s.type === 'pdf') return `📄 ${s.file} (第${s.page}页)`;
                    if (s.type === 'mysql') return `🗄️ ${s.table || 'MySQL数据库'}`;
                    if (s.type === 'excel') return `📊 Excel数据`;
                    return `📎 ${s.type}`;
                });
                content += sources.join(', ');
            }
            
            // 添加预警信息
            if (result.data.warnings && result.data.warnings.length > 0) {
                content = formatWarnings(result.data.warnings) + '\n\n' + content;
            }
            
            appendMessage('assistant', content);
        } else {
            appendMessage('assistant', '抱歉，处理请求时出现错误。');
        }
    } catch (error) {
        loadingMsg.remove();
        appendMessage('assistant', `❌ 错误: ${error.message}`);
    }
}

function appendMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.innerHTML = `<div class="message-content">${formatMarkdown(content)}</div>`;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
}

function formatWarnings(warnings) {
    return warnings.map(w => {
        const severity = w.severity === 'emergency' || w.severity === 'critical' ? 'critical' : '';
        return `<div class="warning-box ${severity}">
            <h4>⚠️ ${w.type}</h4>
            <p>${w.message}</p>
            <p><em>${w.recommendation}</em></p>
        </div>`;
    }).join('');
}

// 事件监听
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

clearHistoryBtn.addEventListener('click', async () => {
    try {
        await apiCall('/api/clear-history', { method: 'POST' });
        chatMessages.innerHTML = '';
        appendMessage('system', '对话历史已清空。您可以开始新的对话。');
    } catch (error) {
        console.error('清空历史失败:', error);
    }
});

// ==================== PDF 结构 ====================

document.getElementById('load-pdf-structure').addEventListener('click', async () => {
    showLoading('pdf-structure-result');
    
    try {
        const result = await apiCall('/api/pdf-structure');
        
        if (result.success) {
            let content = '## 📄 PDF 目录结构\n\n';
            
            if (result.data.toc && result.data.toc.length > 0) {
                content += '### 目录\n';
                result.data.toc.forEach(item => {
                    const indent = '  '.repeat(item.level - 1);
                    content += `${indent}- ${item.title} (来源: ${item.source})\n`;
                });
            } else {
                content += '未提取到目录结构\n';
            }
            
            content += '\n### 表格数量\n';
            content += `共提取到 ${result.data.tables?.length || 0} 个表格\n`;
            
            if (result.data.tables && result.data.tables.length > 0) {
                content += '\n### 表格列表\n';
                result.data.tables.slice(0, 10).forEach((table, i) => {
                    content += `- 表格 ${i + 1}: 来源 ${table.source}, 第 ${table.page} 页\n`;
                });
                if (result.data.tables.length > 10) {
                    content += `\n... 及其他 ${result.data.tables.length - 10} 个表格`;
                }
            }
            
            showResult('pdf-structure-result', content);
        }
    } catch (error) {
        showError('pdf-structure-result', error.message);
    }
});

// ==================== 术语映射 ====================

document.getElementById('normalize-term-btn').addEventListener('click', async () => {
    const term = document.getElementById('term-input').value.trim();
    if (!term) {
        alert('请输入要标准化的术语');
        return;
    }
    
    showLoading('term-result');
    
    try {
        const result = await apiCall('/api/term-normalize', {
            method: 'POST',
            body: JSON.stringify({ term })
        });
        
        if (result.success) {
            let content = `## 术语标准化结果\n\n`;
            content += `**原始术语:** ${result.data.original}\n`;
            content += `**标准术语:** ${result.data.normalized}\n`;
            content += `**是否映射:** ${result.data.is_mapped ? '是' : '否'}\n`;
            
            if (result.data.suggestions && result.data.suggestions.length > 0) {
                content += `\n### 相似术语建议\n`;
                result.data.suggestions.forEach(s => {
                    content += `- ${s.term} → ${s.standard} (相似度: ${s.similarity})\n`;
                });
            }
            
            showResult('term-result', content);
        }
    } catch (error) {
        showError('term-result', error.message);
    }
});

document.getElementById('load-mapping-table-btn').addEventListener('click', async () => {
    showLoading('term-result');
    
    try {
        const result = await apiCall('/api/term-mapping');
        
        if (result.success) {
            let content = '## 📖 术语映射表\n\n';
            content += '| 标准术语 | 别名数量 | 别名列表 |\n';
            content += '|---------|---------|--------|\n';
            
            Object.entries(result.data).forEach(([standard, info]) => {
                const aliases = info.aliases.slice(0, 3).join(', ');
                const more = info.aliases.length > 3 ? `... +${info.aliases.length - 3}` : '';
                content += `| ${standard} | ${info.count} | ${aliases}${more} |\n`;
            });
            
            showResult('term-result', content);
        }
    } catch (error) {
        showError('term-result', error.message);
    }
});

// ==================== 胰岛素分析 ====================

document.getElementById('load-insulin-analysis').addEventListener('click', async () => {
    showLoading('insulin-analysis-result');
    
    try {
        const result = await apiCall('/api/insulin-analysis');
        
        if (result.success && result.data) {
            const data = result.data;
            let content = `## 📊 胰岛素使用率分析\n\n`;
            content += `**数据来源:** ${data.source}\n`;
            content += `**总人数:** ${data.total_patients} 人（糖尿病患者）\n\n`;
            
            if (data.insulin_usage) {
                content += `### 胰岛素使用情况\n`;
                content += `- 使用胰岛素: ${data.insulin_usage.using_insulin} 人\n`;
                content += `- 未使用胰岛素: ${data.insulin_usage.not_using_insulin} 人\n`;
                content += `- **使用率: ${data.insulin_usage.usage_rate}%**\n\n`;
            }
            
            if (data.gender_distribution) {
                content += `### 性别分布\n`;
                Object.entries(data.gender_distribution).forEach(([gender, count]) => {
                    content += `- ${gender}: ${count} 人\n`;
                });
                content += '\n';
            }
            
            if (data.insulin_by_gender) {
                content += `### 按性别的胰岛素使用率\n`;
                Object.entries(data.insulin_by_gender).forEach(([gender, info]) => {
                    content += `- ${gender}: ${info.using}/${info.total} (${info.rate}%)\n`;
                });
                content += '\n';
            }
            
            if (data.age_distribution) {
                content += `### 年龄分布\n`;
                Object.entries(data.age_distribution).forEach(([range, count]) => {
                    content += `- ${range}: ${count} 人\n`;
                });
            }
            
            if (data.age_statistics) {
                content += `\n### 年龄统计\n`;
                content += `- 平均年龄: ${data.age_statistics.mean} 岁\n`;
                content += `- 年龄范围: ${data.age_statistics.min} - ${data.age_statistics.max} 岁\n`;
            }
            
            showResult('insulin-analysis-result', content);
            
            // 绘制简单的图表
            drawInsulinChart(data);
        }
    } catch (error) {
        showError('insulin-analysis-result', error.message);
    }
});

function drawInsulinChart(data) {
    const chartContainer = document.getElementById('insulin-chart');
    if (!data.gender_distribution) {
        chartContainer.innerHTML = '';
        return;
    }
    
    let chartHtml = '<h3>📊 性别分布可视化</h3><div style="display: flex; gap: 20px; align-items: flex-end; height: 200px; padding: 20px;">';
    
    const total = Object.values(data.gender_distribution).reduce((a, b) => a + b, 0);
    const colors = ['#60a5fa', '#f472b6', '#34d399'];
    let colorIndex = 0;
    
    Object.entries(data.gender_distribution).forEach(([gender, count]) => {
        const percentage = (count / total * 100).toFixed(1);
        const height = (count / total * 150);
        chartHtml += `
            <div style="text-align: center;">
                <div style="height: ${height}px; width: 80px; background: ${colors[colorIndex % colors.length]}; border-radius: 8px 8px 0 0;"></div>
                <div style="margin-top: 8px; font-weight: 500;">${gender}</div>
                <div style="color: var(--text-secondary); font-size: 0.85rem;">${count}人 (${percentage}%)</div>
            </div>
        `;
        colorIndex++;
    });
    
    chartHtml += '</div>';
    chartContainer.innerHTML = chartHtml;
}

// ==================== 指南查询 ====================

document.getElementById('query-guidelines-btn').addEventListener('click', async () => {
    const diseaseType = document.getElementById('disease-type-filter').value;
    const updateDate = document.getElementById('update-date-filter').value;
    
    showLoading('guidelines-result');
    
    try {
        let url = '/api/guidelines?';
        if (diseaseType) url += `disease_type=${encodeURIComponent(diseaseType)}&`;
        if (updateDate) url += `update_date_after=${updateDate}`;
        
        const result = await apiCall(url);
        
        if (result.success) {
            if (result.data.length === 0) {
                showResult('guidelines-result', '未找到符合条件的指南推荐');
                return;
            }
            
            let content = `## 📋 指南推荐查询结果\n\n`;
            content += `共找到 ${result.data.length} 条推荐\n\n`;
            
            result.data.forEach((g, i) => {
                content += `### ${i + 1}. ${g.guideline_name}\n`;
                content += `**疾病类型:** ${g.disease_type}\n`;
                content += `**适用条件:** ${g.patient_condition}\n`;
                content += `**推荐等级:** ${g.recommendation_level}\n`;
                content += `**推荐内容:** ${g.recommendation_content}\n`;
                content += `**证据来源:** ${g.evidence_source}\n`;
                content += `**更新日期:** ${g.update_date}\n\n`;
            });
            
            showResult('guidelines-result', content);
        }
    } catch (error) {
        showError('guidelines-result', error.message);
    }
});

// ==================== 患者画像 ====================

document.getElementById('query-patient-btn').addEventListener('click', async () => {
    const patientId = document.getElementById('patient-id-input').value.trim();
    if (!patientId) {
        alert('请输入患者ID');
        return;
    }
    
    showLoading('patient-result');
    
    try {
        const result = await apiCall(`/api/patient/${encodeURIComponent(patientId)}`);
        
        if (result.success && result.data) {
            let content = result.data.answer || '查询完成';
            
            // 添加预警
            if (result.data.warnings && result.data.warnings.length > 0) {
                content = formatWarnings(result.data.warnings) + '\n\n' + content;
            }
            
            showResult('patient-result', content);
        }
    } catch (error) {
        showError('patient-result', error.message);
    }
});

// ==================== 风险评估 ====================

document.getElementById('assess-risk-btn').addEventListener('click', async () => {
    const patientId = document.getElementById('risk-patient-id-input').value.trim();
    if (!patientId) {
        alert('请输入患者ID');
        return;
    }
    
    showLoading('risk-result');
    
    try {
        const result = await apiCall(`/api/patient/${encodeURIComponent(patientId)}/risk-assessment`);
        
        if (result.success && result.data) {
            const data = result.data;
            let content = `## ⚠️ 风险评估报告\n\n`;
            content += `**患者ID:** ${data.patient_id}\n`;
            content += `**综合风险等级:** ${data.overall_risk || '未评估'}\n\n`;
            
            if (data.assessments) {
                // 高血压评估
                const hp = data.assessments.hypertension;
                if (hp) {
                    content += `### 🩺 高血压风险评估\n`;
                    content += `**风险等级:** ${hp.risk_level}\n`;
                    if (hp.bp_classification) {
                        content += `**血压分级:** ${hp.bp_classification.name}\n`;
                    }
                    if (hp.risk_factors && hp.risk_factors.length > 0) {
                        content += `**危险因素:** ${hp.risk_factors.join(', ')}\n`;
                    }
                    if (hp.follow_up_plan) {
                        content += `\n**随访计划:**\n`;
                        content += `- 频率: ${hp.follow_up_plan.frequency}\n`;
                        content += `- 下次随访: ${hp.follow_up_plan.next_visit}\n`;
                        content += `- 监测项目: ${hp.follow_up_plan.monitoring?.join(', ')}\n`;
                    }
                    content += `\n*证据等级: ${hp.evidence_level}, 来源: ${hp.source}*\n\n`;
                }
                
                // 糖尿病评估
                const dm = data.assessments.diabetes;
                if (dm) {
                    content += `### 🍬 糖尿病控制评估\n`;
                    content += `**控制状态:** ${dm.control_status}\n`;
                    if (dm.hba1c_classification) {
                        content += `**HbA1c分级:** ${dm.hba1c_classification.level} - ${dm.hba1c_classification.description}\n`;
                    }
                    if (dm.follow_up_plan) {
                        content += `\n**随访计划:**\n`;
                        content += `- 频率: ${dm.follow_up_plan.frequency}\n`;
                        content += `- 下次随访: ${dm.follow_up_plan.next_visit}\n`;
                    }
                    content += `\n*证据等级: ${dm.evidence_level}, 来源: ${dm.source}*\n`;
                }
            }
            
            showResult('risk-result', content);
        }
    } catch (error) {
        showError('risk-result', error.message);
    }
});

// ==================== 诊断推理 ====================

document.getElementById('diagnosis-btn').addEventListener('click', async () => {
    const input = document.getElementById('diagnosis-input').value.trim();
    if (!input) {
        alert('请输入症状和检查数据');
        return;
    }
    
    showLoading('diagnosis-result');
    
    try {
        const result = await apiCall('/api/chat', {
            method: 'POST',
            body: JSON.stringify({ message: `请进行诊断推理分析：${input}` })
        });
        
        if (result.success && result.data) {
            let content = result.data.answer || result.data;
            
            if (result.data.sources && result.data.sources.length > 0) {
                content += '\n\n---\n**参考来源:** ';
                content += result.data.sources.map(s => `${s.type}: ${s.file || s.table}`).join(', ');
            }
            
            showResult('diagnosis-result', content);
        }
    } catch (error) {
        showError('diagnosis-result', error.message);
    }
});

// ==================== 治疗方案 ====================

document.getElementById('treatment-btn').addEventListener('click', async () => {
    const patientId = document.getElementById('treatment-patient-id').value.trim();
    const input = document.getElementById('treatment-input').value.trim();
    
    if (!input) {
        alert('请描述患者病情');
        return;
    }
    
    showLoading('treatment-result');
    
    try {
        const result = await apiCall('/api/chat', {
            method: 'POST',
            body: JSON.stringify({ 
                message: `请生成治疗方案：${input}`,
                patient_id: patientId || null
            })
        });
        
        if (result.success && result.data) {
            let content = result.data.answer || result.data;
            
            // 添加预警
            if (result.data.warnings && result.data.warnings.length > 0) {
                content = formatWarnings(result.data.warnings) + '\n\n' + content;
            }
            
            if (result.data.sources && result.data.sources.length > 0) {
                content += '\n\n---\n**参考来源:** ';
                content += result.data.sources.map(s => `${s.type}: ${s.file || s.table}`).join(', ');
            }
            
            showResult('treatment-result', content);
        }
    } catch (error) {
        showError('treatment-result', error.message);
    }
});

// ==================== 索引管理 ====================

document.getElementById('check-index-status-btn').addEventListener('click', async () => {
    try {
        const result = await apiCall('/api/index/status');
        
        if (result.success) {
            const status = result.data;
            let html = `<p><strong>索引状态:</strong> ${status.has_index ? '✅ 已加载' : '❌ 未加载'}</p>`;
            html += `<p><strong>最后更新:</strong> ${status.last_update || '从未更新'}</p>`;
            html += `<p><strong>存储路径:</strong> ${status.persist_path}</p>`;
            document.getElementById('index-status').innerHTML = html;
        }
    } catch (error) {
        document.getElementById('index-status').innerHTML = `<p class="error">获取状态失败: ${error.message}</p>`;
    }
});

document.getElementById('rebuild-index-btn').addEventListener('click', async () => {
    if (!confirm('确定要重建索引吗？这可能需要几分钟时间。')) {
        return;
    }
    
    showLoading('index-result');
    
    try {
        const result = await apiCall('/api/index/rebuild', { method: 'POST' });
        
        if (result.success) {
            let content = `## ✅ 索引重建成功\n\n`;
            content += `**时间戳:** ${result.data.timestamp}\n`;
            content += `**消息:** ${result.data.message}\n`;
            showResult('index-result', content);
            
            // 刷新状态
            document.getElementById('check-index-status-btn').click();
        } else {
            showError('index-result', result.data?.message || '重建失败');
        }
    } catch (error) {
        showError('index-result', error.message);
    }
});

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    console.log('医疗知识助手前端已加载');
});

