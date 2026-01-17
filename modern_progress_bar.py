"""
MODERN PROGRESS BAR - Schönes Design für Liga-Analyse
Ersetzt den orangenen Blob mit professionellem Progress Bar
"""

import streamlit as st
import time
from typing import List, Optional


class ModernProgressBar:
    """
    Moderner, animierter Progress Bar für Liga-Analyse
    """
    
    def __init__(self, total_items: int, title: str = "Analyzing Leagues"):
        self.total_items = total_items
        self.current_item = 0
        self.title = title
        self.start_time = time.time()
        
        # Streamlit UI Elements (werden einmal erstellt)
        self.title_placeholder = st.empty()
        self.progress_bar = st.empty()
        self.status_placeholder = st.empty()
        self.stats_placeholder = st.empty()
        
        # Initial render
        self._render()
    
    def update(self, current_league: str, current_index: int):
        """
        Update Progress Bar mit aktueller Liga
        
        Args:
            current_league: Name der aktuell analysierenden Liga (z.B. "BL1", "PL", etc.)
            current_index: Index der aktuellen Liga (0-based)
        """
        self.current_item = current_index + 1
        self.current_league = current_league
        self._render()
    
    def _render(self):
        """
        Rendere Progress Bar UI
        """
        # Berechne Fortschritt
        progress = self.current_item / self.total_items if self.total_items > 0 else 0
        percentage = int(progress * 100)
        
        # Berechne geschätzte Zeit
        elapsed_time = time.time() - self.start_time
        if self.current_item > 0:
            avg_time_per_item = elapsed_time / self.current_item
            remaining_items = self.total_items - self.current_item
            estimated_remaining = avg_time_per_item * remaining_items
        else:
            estimated_remaining = 0
        
        # Title mit Emoji
        self.title_placeholder.markdown(f"### 🔄 {self.title}")
        
        # Progress Bar (Streamlit native)
        self.progress_bar.progress(progress)
        
        # Status
        if self.current_item > 0:
            current_league_name = getattr(self, 'current_league', 'Unknown')
            status_text = f"**Currently analyzing:** {current_league_name}"
        else:
            status_text = "**Starting analysis...**"
        
        self.status_placeholder.markdown(status_text)
        
        # Statistics
        col1, col2, col3, col4 = self.stats_placeholder.columns(4)
        
        with col1:
            st.metric(
                label="Progress",
                value=f"{percentage}%",
                delta=None
            )
        
        with col2:
            st.metric(
                label="Completed",
                value=f"{self.current_item}/{self.total_items}",
                delta=None
            )
        
        with col3:
            elapsed_str = self._format_time(elapsed_time)
            st.metric(
                label="Elapsed",
                value=elapsed_str,
                delta=None
            )
        
        with col4:
            remaining_str = self._format_time(estimated_remaining)
            st.metric(
                label="Remaining",
                value=remaining_str,
                delta=None
            )
    
    def _format_time(self, seconds: float) -> str:
        """
        Formatiere Zeit in lesbares Format
        """
        if seconds < 1:
            return "< 1s"
        elif seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def complete(self, success_message: Optional[str] = None):
        """
        Zeige Completion Message
        """
        self.progress_bar.progress(1.0)
        
        if success_message:
            self.status_placeholder.success(success_message)
        else:
            elapsed = time.time() - self.start_time
            self.status_placeholder.success(
                f"✅ Analysis complete! Processed {self.total_items} leagues in {self._format_time(elapsed)}"
            )
        
        # Clear stats after completion
        time.sleep(1)
        self.stats_placeholder.empty()


class CompactProgressBar:
    """
    Kompakter Progress Bar für kleinere Spaces
    """
    
    def __init__(self, total_items: int):
        self.total_items = total_items
        self.current_item = 0
        
        # Single placeholder
        self.placeholder = st.empty()
    
    def update(self, current_league: str, current_index: int):
        """
        Update mit aktueller Liga
        """
        self.current_item = current_index + 1
        progress = self.current_item / self.total_items
        percentage = int(progress * 100)
        
        with self.placeholder.container():
            st.progress(progress)
            st.caption(f"Analyzing {current_league}... ({self.current_item}/{self.total_items}) - {percentage}%")
    
    def complete(self, message: str = "✅ Complete!"):
        """
        Completion
        """
        self.placeholder.success(message)


class MinimalProgressBar:
    """
    Minimaler Progress Bar - nur Balken
    """
    
    def __init__(self, total_items: int):
        self.total_items = total_items
        self.bar = st.progress(0)
        self.text = st.empty()
    
    def update(self, current_league: str, current_index: int):
        """
        Update
        """
        progress = (current_index + 1) / self.total_items
        self.bar.progress(progress)
        self.text.text(f"Analyzing {current_league}...")
    
    def complete(self):
        """
        Complete
        """
        self.bar.progress(1.0)
        self.text.success("✅ Analysis complete!")


# Utility Functions
def create_league_progress_bar(
    leagues: List[str],
    style: str = "modern"
) -> ModernProgressBar:
    """
    Factory function für Progress Bar
    
    Args:
        leagues: Liste der zu analysierenden Ligen
        style: "modern", "compact", oder "minimal"
    
    Returns:
        Progress Bar instance
    """
    total = len(leagues)
    
    if style == "modern":
        return ModernProgressBar(total, title="Analyzing Leagues")
    elif style == "compact":
        return CompactProgressBar(total)
    elif style == "minimal":
        return MinimalProgressBar(total)
    else:
        return ModernProgressBar(total)


# Example Usage
def demo_progress_bar():
    """
    Demo der verschiedenen Progress Bar Styles
    """
    st.title("Progress Bar Styles Demo")
    
    style = st.selectbox(
        "Select Style",
        ["modern", "compact", "minimal"]
    )
    
    leagues = ["BL1", "PL", "PD", "SA", "FL1", "DED", "PPL", "TSL"]
    
    if st.button("Start Demo"):
        progress = create_league_progress_bar(leagues, style=style)
        
        for idx, league in enumerate(leagues):
            progress.update(league, idx)
            time.sleep(0.5)  # Simulate processing
        
        progress.complete()
        st.balloons()


if __name__ == "__main__":
    demo_progress_bar()
