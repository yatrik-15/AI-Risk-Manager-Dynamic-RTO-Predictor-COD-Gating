// AddToCartEffect.jsx
//
// Single-file version: hook + ProductCard + CartIcon all in one.
// Drop this into frontend/src/components/AddToCartEffect.jsx
//
// Setup:
//   npm install gsap
//
// Usage in Checkout.jsx:
//   import { ProductCard, CartIcon } from "./components/AddToCartEffect";
//
//   <CartIcon count={cartCount} />
//   {products.map(p => (
//     <ProductCard key={p.id} product={p} onAddToCart={handleAddToCart} />
//   ))}

import { useCallback, useRef } from "react";
import gsap from "gsap";

// ---------------------------------------------------------------------------
// Hook: useAddToCartEffect
// Moves product to center, shows checkout card animation, then shipping truck
// before flying to the cart icon.
// ---------------------------------------------------------------------------
function useAddToCartEffect({ veilOpacity = 1 } = {}) {
  const triggerAddToCartEffect = useCallback(
    ({ imageEl, buttonEl, cartEl, onLanded }) => {
      if (!imageEl || !cartEl) return;

      const imgRect = imageEl.getBoundingClientRect();
      const cartRect = cartEl.getBoundingClientRect();
      const cartCenterX = cartRect.left + cartRect.width / 2;
      const cartCenterY = cartRect.top + cartRect.height / 2;
      
      const windowCenterX = window.innerWidth / 2;
      const windowCenterY = window.innerHeight / 2;

      const fxLayer = document.createElement("div");
      Object.assign(fxLayer.style, {
        position: "fixed",
        inset: "0",
        pointerEvents: "none",
        zIndex: 9999,
      });
      document.body.appendChild(fxLayer);

      const veil = document.createElement("div");
      Object.assign(veil.style, {
        position: "fixed",
        inset: "0",
        background: "var(--atc-veil-color, rgba(255, 255, 255, 0.85))",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        opacity: "0",
        pointerEvents: "none",
        zIndex: 9998,
      });
      document.body.appendChild(veil);

      // Create clone of product image
      const cloneImg = document.createElement("img");
      cloneImg.src = imageEl.src;
      Object.assign(cloneImg.style, {
        position: "absolute",
        width: `${imgRect.width}px`,
        height: `${imgRect.height}px`,
        left: `${imgRect.left}px`,
        top: `${imgRect.top}px`,
        borderRadius: "12px",
        boxShadow: "0 20px 40px rgba(0,0,0,0.15)",
        objectFit: "cover",
      });
      fxLayer.appendChild(cloneImg);

      // Helper to create an icon element
      const createIcon = (svgString, size, offsetX, offsetY) => {
        const el = document.createElement("div");
        el.innerHTML = svgString;
        Object.assign(el.style, {
          position: "absolute",
          left: `${windowCenterX + offsetX - size/2}px`,
          top: `${windowCenterY + offsetY - size/2}px`,
          width: `${size}px`,
          height: `${size}px`,
          color: "var(--atc-icon-color, #111)",
          opacity: 0,
          transform: "scale(0)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          filter: "drop-shadow(0px 8px 16px rgba(0,0,0,0.1))"
        });
        fxLayer.appendChild(el);
        return el;
      };

      const cartSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg>`;
      const stageCart = createIcon(cartSvg, 64, 0, 40);

      const cardSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>`;
      const stageCard = createIcon(cardSvg, 48, 60, -20);

      // Shared text styles
      const textStyle = {
        position: "absolute",
        left: "0",
        top: `${windowCenterY + 100}px`,
        width: "100%",
        textAlign: "center",
        color: "var(--atc-icon-color, #111)",
        fontSize: "20px",
        fontWeight: "600",
        fontFamily: "sans-serif",
        opacity: 0,
      };

      const checkoutText = document.createElement("div");
      checkoutText.innerText = "Processing Checkout...";
      Object.assign(checkoutText.style, textStyle);
      fxLayer.appendChild(checkoutText);

      const cleanup = () => {
        fxLayer.remove();
        gsap.to(veil, {
          opacity: 0,
          duration: 0.3,
          onComplete: () => veil.remove(),
        });
      };

      const tl = gsap.timeline({ onComplete: cleanup });

      // 1. Dim background
      tl.to(veil, { opacity: veilOpacity, duration: 0.3 }, 0);

      // 2. Button micro-feedback
      if (buttonEl) {
        gsap.fromTo(
          buttonEl,
          { scale: 1 },
          { scale: 0.94, duration: 0.1, yoyo: true, repeat: 1 }
        );
      }

      // 3. Image moves to center and scales down, cart appears
      const dxImg = windowCenterX - (imgRect.left + imgRect.width / 2);
      const dyImg = windowCenterY - (imgRect.top + imgRect.height / 2) - 60;

      tl.to(cloneImg, {
        x: dxImg,
        y: dyImg,
        scale: 0.35,
        duration: 0.6,
        ease: "power3.out"
      }, 0.1);
      
      tl.to(stageCart, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.5)" }, 0.3);

      // Image drops into cart
      tl.to(cloneImg, {
        y: dyImg + 80,
        scale: 0.1,
        opacity: 0,
        duration: 0.4,
        ease: "power2.in"
      }, 0.7);

      tl.to(stageCart, { scale: 1.15, yoyo: true, repeat: 1, duration: 0.15 }, 1.0);

      // 4. Checkout Process
      tl.to(checkoutText, { opacity: 1, y: -10, duration: 0.3 }, 1.1);
      tl.fromTo(stageCard,
        { x: 40, y: -40, opacity: 0, rotation: 15, scale: 1 },
        { x: -10, y: 0, opacity: 1, rotation: -10, duration: 0.4, ease: "power2.out" },
        1.1
      );
      // Swipe card down
      tl.to(stageCard, { y: 30, opacity: 0, duration: 0.3, ease: "power2.in" }, 1.6);
      tl.to(stageCart, { scale: 1.15, yoyo: true, repeat: 1, duration: 0.15 }, 1.8);
      tl.to(checkoutText, { opacity: 0, y: -20, duration: 0.3 }, 1.8);

      // 5. Move Cart to actual cart icon
      const dxCart = cartCenterX - windowCenterX;
      const dyCart = cartCenterY - (windowCenterY + 40);

      tl.to(stageCart, {
        x: dxCart,
        y: dyCart,
        scale: 0.3,
        opacity: 0,
        duration: 0.7,
        ease: "power2.inOut"
      }, 2.0);

      // 6. Cart bump
      tl.call(
        () => {
          gsap.fromTo(
            cartEl,
            { scale: 1 },
            { scale: 1.25, duration: 0.15, yoyo: true, repeat: 1, ease: "power1.inOut" }
          );
          onLanded?.();
        },
        null,
        2.7
      );
    },
    [veilOpacity]
  );

  return { triggerAddToCartEffect };
}

function useShippingEffect({ veilOpacity = 1 } = {}) {
  const triggerShippingEffect = useCallback(
    ({ onLanded }) => {
      const windowCenterX = window.innerWidth / 2;
      const windowCenterY = window.innerHeight / 2;

      const fxLayer = document.createElement("div");
      Object.assign(fxLayer.style, {
        position: "fixed",
        inset: "0",
        pointerEvents: "none",
        zIndex: 9999,
      });
      document.body.appendChild(fxLayer);

      const veil = document.createElement("div");
      Object.assign(veil.style, {
        position: "fixed",
        inset: "0",
        background: "var(--atc-veil-color, rgba(255, 255, 255, 0.85))",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        opacity: "0",
        pointerEvents: "none",
        zIndex: 9998,
      });
      document.body.appendChild(veil);

      // Create Truck icon
      const createIcon = (svgString, size) => {
        const el = document.createElement("div");
        el.innerHTML = svgString;
        Object.assign(el.style, {
          position: "absolute",
          left: `${windowCenterX - size/2}px`,
          top: `${windowCenterY - size/2}px`,
          width: `${size}px`,
          height: `${size}px`,
          color: "var(--atc-icon-color, #111)",
          opacity: 0,
          transform: "scale(0)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          filter: "drop-shadow(0px 8px 16px rgba(0,0,0,0.1))"
        });
        fxLayer.appendChild(el);
        return el;
      };

      const truckSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>`;
      const stageTruck = createIcon(truckSvg, 96);

      const textStyle = {
        position: "absolute",
        left: "0",
        top: `${windowCenterY + 80}px`,
        width: "100%",
        textAlign: "center",
        color: "var(--atc-icon-color, #111)",
        fontSize: "24px",
        fontWeight: "600",
        fontFamily: "sans-serif",
        opacity: 0,
      };

      const shippingText = document.createElement("div");
      shippingText.innerText = "Shipping Details Verified!";
      Object.assign(shippingText.style, textStyle);
      fxLayer.appendChild(shippingText);

      const cleanup = () => {
        fxLayer.remove();
        gsap.to(veil, {
          opacity: 0,
          duration: 0.3,
          onComplete: () => veil.remove(),
        });
      };

      const tl = gsap.timeline({ onComplete: cleanup });

      // 1. Dim background
      tl.to(veil, { opacity: veilOpacity, duration: 0.3 }, 0);

      // 2. Show Truck and text
      tl.to(stageTruck, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.5)" }, 0.2);
      tl.to(shippingText, { opacity: 1, y: -10, duration: 0.3 }, 0.4);

      // 3. Truck revs up and drives away to the right
      tl.to(stageTruck, { x: -30, duration: 0.3, ease: "power1.inOut" }, 1.0);
      tl.to(shippingText, { opacity: 0, y: -20, duration: 0.3 }, 1.3);
      tl.to(stageTruck, {
        x: window.innerWidth / 2 + 150,
        opacity: 0,
        duration: 0.6,
        ease: "power2.in"
      }, 1.4);

      // 4. Finish
      tl.call(
        () => {
          onLanded?.();
        },
        null,
        2.0
      );
    },
    [veilOpacity]
  );

  return { triggerShippingEffect };
}

// ---------------------------------------------------------------------------
// Component: ProductCard
// Wraps a product image + "Add to cart" button and fires the effect on click.
// ---------------------------------------------------------------------------
function ProductCard({ product, onAddToCart }) {
  const imgRef = useRef(null);
  const btnRef = useRef(null);
  const { triggerAddToCartEffect } = useAddToCartEffect();

  const handleAddToCart = () => {
    triggerAddToCartEffect({
      imageEl: imgRef.current,
      buttonEl: btnRef.current,
      cartEl: document.getElementById("cart-icon"),
      onLanded: () => onAddToCart?.(product),
    });
  };

  return (
    <div className="card">
      <div className="card-media">
        <img ref={imgRef} src={product.image} alt={product.name} />
      </div>
      <button ref={btnRef} className="add-btn" onClick={handleAddToCart}>
        Add to cart
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component: CartIcon
// Must carry id="cart-icon" — the hook looks it up by this id as the
// animation's landing target. Render this once, anywhere in your layout.
// ---------------------------------------------------------------------------
function CartIcon({ count = 0 }) {
  return (
    <div id="cart-icon" className="cart-pill">
      Cart <span className="cart-count">{count}</span>
    </div>
  );
}

export { useAddToCartEffect, useShippingEffect, ProductCard, CartIcon };
