// javascript to make the tabs to work

const reg_form = document.querySelector("#registration-form");
const login_form = document.querySelector("#login-form");

const reg_tab = document.querySelector('.reg-tab');
const login_tab = document.querySelector('.login-tab');

reg_tab.addEventListener('click', e => {
    login_form.style.display = 'none';
    reg_form.style.display = 'block';
    reg_tab.classList.add('active');
    login_tab.classList.remove('active')
})
login_tab.addEventListener('click', e => {
    reg_form.style.display = 'none';
    login_form.style.display = 'block';
    reg_tab.classList.remove('active');
    login_tab.classList.add('active')
})

