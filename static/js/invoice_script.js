document.addEventListener('DOMContentLoaded', () => {
    const primaryColorInput = document.getElementById('primaryColor');
    const secondaryColorInput = document.getElementById('secondaryColor');
    const root = document.querySelector(':root');

    // Update colors
    primaryColorInput.addEventListener('input', (e) => {
        root.style.setProperty('--primary-color', e.target.value);
    });

    secondaryColorInput.addEventListener('input', (e) => {
        root.style.setProperty('--secondary-color', e.target.value);
    });

    // Handle Editable Content
    const editables = document.querySelectorAll('[contenteditable="true"]');
    editables.forEach(el => {
        el.addEventListener('blur', () => {
            // Optional: Save to local storage or sync with backend
            console.log(`Content updated for ${el.className}`);
        });
    });
});

function printInvoice() {
    window.print();
}
