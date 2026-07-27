/**
 * The last line of defence for graceful degradation.
 *
 * A render error inside an iframe is invisible from the host page: Streamlit
 * has no way to know the component threw, and the reader gets a blank box. So
 * the component catches its own errors and prints a plain sentence instead.
 * The page underneath repeats every figure in prose regardless, so a reader
 * who sees this fallback still gets the finding, just not the picture.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  failed: boolean;
}

export class Boundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surfaces in the browser console during development; never to the reader.
    console.error("contribution list failed to render", error, info);
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <p style={{ font: "13px/1.5 system-ui", margin: 0, opacity: 0.8 }}>
          This list could not be drawn. The reasons it would have shown are
          written out in the sentences below it.
        </p>
      );
    }
    return this.props.children;
  }
}
