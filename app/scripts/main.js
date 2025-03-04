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

    // Mobile menu functionality
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    const body = document.body;

    // Create overlay element
    const overlay = document.createElement('div');
    overlay.className = 'menu-overlay';
    body.appendChild(overlay);

    function toggleMenu() {
        menuToggle.classList.toggle('active');
        navLinks.classList.toggle('active');
        overlay.classList.toggle('active');
        body.style.overflow = body.style.overflow === 'hidden' ? '' : 'hidden';
    }

    menuToggle.addEventListener('click', toggleMenu);
    overlay.addEventListener('click', toggleMenu);

    // Close menu when clicking a link
    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => {
        link.addEventListener('click', () => {
            if (navLinks.classList.contains('active')) {
                toggleMenu();
            }
        });
    });

    // Close menu on window resize if open
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && navLinks.classList.contains('active')) {
            toggleMenu();
        }
    });
});