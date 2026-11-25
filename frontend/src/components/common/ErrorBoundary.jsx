import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    if (import.meta.env.DEV) {
      console.error('BizPermit UI ErrorBoundary caught:', error, errorInfo);
    }
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      const showDevDetails = import.meta.env.DEV && this.state.error;
      return (
        <div className="min-h-screen bg-brand-cream flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white rounded-xl border border-stone-200 shadow-lg p-6 text-center space-y-4">
            <div className="mx-auto w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center">
              <AlertTriangle className="h-6 w-6 text-amber-600" />
            </div>
            <h1 className="text-lg font-bold text-brand-charcoal">
              Something went wrong
            </h1>
            <p className="text-sm text-stone-600">
              An unexpected interface error occurred. Your compliance data is safe. Please reload the page or return to the home workspace.
            </p>
            {showDevDetails && (
              <pre className="text-left text-xs bg-stone-100 text-rose-700 p-3 rounded border border-stone-200 overflow-x-auto max-h-40">
                {this.state.error.message || String(this.state.error)}
              </pre>
            )}
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReload}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-deep-sage text-white text-sm font-semibold hover:opacity-90 transition-opacity"
              >
                <RefreshCw className="h-4 w-4" />
                Reload Page
              </button>
              <button
                type="button"
                onClick={this.handleGoHome}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-stone-300 text-stone-700 text-sm font-semibold hover:bg-stone-50 transition-colors"
              >
                <Home className="h-4 w-4" />
                Home
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
