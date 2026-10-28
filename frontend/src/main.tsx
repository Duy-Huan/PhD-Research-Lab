import React from 'react';
import ReactDOM from 'react-dom/client';
import './shared/i18n';
import { App } from './app/App';
import { restoreSavedTheme } from './features/settings/SettingsModal';

restoreSavedTheme();  // before the first render, so a dark theme does not flash light

// Guard against Three.js / Drei / KaTeX DOM portal unmount race conditions
if (typeof Node !== 'undefined' && Node.prototype) {
  const originalRemoveChild = Node.prototype.removeChild;
  Node.prototype.removeChild = function <T extends Node>(child: T): T {
    if (child.parentNode !== this) {
      if (child.parentNode) {
        return child.parentNode.removeChild(child);
      }
      return child;
    }
    return originalRemoveChild.call(this, child) as T;
  };
}

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
