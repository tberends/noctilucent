document.addEventListener('DOMContentLoaded', () => {
    const figuresContainer = document.getElementById('figures-container');
    const htmlFiles = [
        'sounding_plot.html',
        // Add more HTML filenames here
    ];

    htmlFiles.forEach(file => {
        const iframe = document.createElement('iframe');
        iframe.src = `app/visualizations/${file}`;
        iframe.width = '100%';
        iframe.height = '1000px';
        iframe.style.border = 'none';
        figuresContainer.appendChild(iframe);
    });
});