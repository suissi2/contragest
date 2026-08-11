document.addEventListener('DOMContentLoaded', () => {
    // Animate map dots randomly for a "live" feel
    const dots = document.querySelectorAll('.dot');
    
    setInterval(() => {
        dots.forEach(dot => {
            // Randomly shift possession slightly
            const currentTop = parseFloat(dot.style.top);
            const currentLeft = parseFloat(dot.style.left);
            
            const newTop = currentTop + (Math.random() * 4 - 2);
            const newLeft = currentLeft + (Math.random() * 4 - 2);
            
            // Keep within bounds
            if (newTop > 10 && newTop < 90) dot.style.top = `${newTop}%`;
            if (newLeft > 10 && newLeft < 90) dot.style.left = `${newLeft}%`;
        });
    }, 2000);

    // Interactive Navigation
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
        });
    });

    // Update real time data simulation
    const timeElements = document.querySelectorAll('.feed-time');
    setInterval(() => {
        const now = new Date();
        const firstTime = now.toLocaleTimeString('en-GB', { hour12: false });
        // Just subtly update the first one
        if (timeElements.length > 0) {
           timeElements[0].textContent = firstTime;
        }
    }, 1000);
});
