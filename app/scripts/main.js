document.addEventListener('DOMContentLoaded', () => {
    const figuresContainer = document.getElementById('figures-container');
    const images = [
        'sounding_plot.png',
        // Add more image filenames here
    ];

    images.forEach(file => {
        const img = document.createElement('img');
        img.src = `app/visualizations/${file}`;
        img.alt = file;
        figuresContainer.appendChild(img);
    });
});