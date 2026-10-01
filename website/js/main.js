/* ============================================
   FinShield AI — Main JavaScript
   Interactions: FAQ, mobile menu, scroll animations
   ============================================ */

(function () {
  'use strict';

  // --- Navigation scroll effect ---
  const nav = document.getElementById('nav');
  let lastScroll = 0;

  function handleNavScroll() {
    const currentScroll = window.pageYOffset;
    if (currentScroll > 20) {
      nav.classList.add('nav--scrolled');
    } else {
      nav.classList.remove('nav--scrolled');
    }
    lastScroll = currentScroll;
  }

  window.addEventListener('scroll', handleNavScroll, { passive: true });

  // --- Mobile menu ---
  const mobileToggle = document.getElementById('mobileToggle');
  const mobileMenu = document.getElementById('mobileMenu');
  const mobileClose = document.getElementById('mobileClose');
  const mobileOverlay = document.getElementById('mobileOverlay');

  function openMobileMenu() {
    mobileMenu.setAttribute('data-open', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeMobileMenu() {
    mobileMenu.setAttribute('data-open', 'false');
    document.body.style.overflow = '';
  }

  if (mobileToggle) mobileToggle.addEventListener('click', openMobileMenu);
  if (mobileClose) mobileClose.addEventListener('click', closeMobileMenu);
  if (mobileOverlay) mobileOverlay.addEventListener('click', closeMobileMenu);

  // Close mobile menu on link click
  document.querySelectorAll('.mobile-menu__link').forEach(function (link) {
    link.addEventListener('click', closeMobileMenu);
  });

  // Close on Escape key
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && mobileMenu.getAttribute('data-open') === 'true') {
      closeMobileMenu();
    }
  });

  // --- FAQ Accordion ---
  document.querySelectorAll('.faq-item__question').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var item = this.closest('.faq-item');
      var isOpen = item.getAttribute('data-open') === 'true';

      // Close all other items
      document.querySelectorAll('.faq-item').forEach(function (otherItem) {
        if (otherItem !== item) {
          otherItem.setAttribute('data-open', 'false');
        }
      });

      // Toggle current item
      item.setAttribute('data-open', isOpen ? 'false' : 'true');
    });
  });

  // --- Scroll-triggered fade-in animations ---
  var fadeElements = document.querySelectorAll('.fade-in');

  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px',
      }
    );

    fadeElements.forEach(function (el) {
      observer.observe(el);
    });
  } else {
    // Fallback: show all elements immediately
    fadeElements.forEach(function (el) {
      el.classList.add('visible');
    });
  }

  // --- Smooth scroll for anchor links ---
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      var targetId = this.getAttribute('href');
      if (targetId === '#') return;

      var target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        var navHeight = nav ? nav.offsetHeight : 0;
        var targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight - 20;

        window.scrollTo({
          top: targetPosition,
          behavior: 'smooth',
        });
      }
    });
  });

  // --- Pipeline diagram animation (hero) ---
  var pipelineStages = document.querySelectorAll('.pipeline-stage');

  if (pipelineStages.length > 0 && 'IntersectionObserver' in window) {
    var pipelineObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animatePipeline();
            pipelineObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.3 }
    );

    var heroDiagram = document.querySelector('.hero__diagram');
    if (heroDiagram) {
      pipelineObserver.observe(heroDiagram);
    }
  }

  function animatePipeline() {
    pipelineStages.forEach(function (stage, index) {
      stage.style.opacity = '0';
      stage.style.transform = 'translateX(-10px)';
      stage.style.transition = 'opacity 0.4s ease ' + (index * 0.15) + 's, transform 0.4s ease ' + (index * 0.15) + 's';

      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          stage.style.opacity = '1';
          stage.style.transform = 'translateX(0)';
        });
      });
    });
  }

  // --- Counter animation for stats ---
  var statValues = document.querySelectorAll('.stat__value');

  if (statValues.length > 0 && 'IntersectionObserver' in window) {
    var statsObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            statsObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.5 }
    );

    statValues.forEach(function (el) {
      statsObserver.observe(el);
    });
  }

  // --- Reveal animations (scroll-triggered) ---
  var revealElements = document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale, .stagger-children');

  if ('IntersectionObserver' in window) {
    var revealObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    );

    revealElements.forEach(function (el) {
      revealObserver.observe(el);
    });
  } else {
    revealElements.forEach(function (el) {
      el.classList.add('visible');
    });
  }

  // --- Magnetic button hover effect ---
  document.querySelectorAll('.btn--magnetic').forEach(function (btn) {
    btn.addEventListener('mousemove', function (e) {
      var rect = this.getBoundingClientRect();
      var x = ((e.clientX - rect.left) / rect.width) * 100;
      var y = ((e.clientY - rect.top) / rect.height) * 100;
      this.style.setProperty('--mouse-x', x + '%');
      this.style.setProperty('--mouse-y', y + '%');
    });
  });

  // --- Glassmorphism tilt effect on cards ---
  document.querySelectorAll('.glass-card-tilt').forEach(function (card) {
    card.addEventListener('mousemove', function (e) {
      var rect = this.getBoundingClientRect();
      var x = (e.clientX - rect.left) / rect.width - 0.5;
      var y = (e.clientY - rect.top) / rect.height - 0.5;
      this.style.transform = 'perspective(800px) rotateY(' + (x * 6) + 'deg) rotateX(' + (-y * 6) + 'deg) translateY(-4px)';
    });
    card.addEventListener('mouseleave', function () {
      this.style.transform = 'perspective(800px) rotateY(0) rotateX(0) translateY(0)';
    });
  });

})();
