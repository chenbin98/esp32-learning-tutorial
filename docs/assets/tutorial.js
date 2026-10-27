// 页面可直接离线打开；复制按钮仅提供便利，失败时保留手动复制。
for (const pre of document.querySelectorAll('pre[data-copy]')) {
  const box = document.createElement('div');
  box.className = 'codebox';
  pre.before(box);
  box.append(pre);
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'copy';
  button.textContent = '复制';
  button.setAttribute('aria-label', '复制这段命令或代码');
  button.addEventListener('click', async () => {
    const text = pre.querySelector('code').textContent;
    try {
      if (!navigator.clipboard) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(text);
      button.textContent = '已复制';
    } catch (_) {
      const range = document.createRange();
      range.selectNodeContents(pre.querySelector('code'));
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = '已选中，请手动复制';
    }
    setTimeout(() => { button.textContent = '复制'; }, 2500);
  });
  box.append(button);
}
