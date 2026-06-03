const reveals = document.querySelectorAll(
  ".hero-copy, .hero-visual, .proof-strip article, .step-card, .examples-art, .example-card, .comparison-card, .feature-card, .ownership-copy, .ownership-art, .pricing-card, .faq-list details, .contact-shell"
);

reveals.forEach((node) => node.classList.add("reveal"));

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.14 }
  );

  reveals.forEach((node) => observer.observe(node));
} else {
  reveals.forEach((node) => node.classList.add("is-visible"));
}
