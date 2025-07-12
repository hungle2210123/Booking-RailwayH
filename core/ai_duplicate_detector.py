"""
AI-Powered Duplicate Detection System
Provides intelligent duplicate filtering right after booking extraction
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import difflib
import re
import json

class AIDuplicateDetector:
    """AI-powered duplicate detection with smart filtering options"""
    
    def __init__(self):
        self.similarity_threshold = 0.8  # Name similarity threshold
        self.date_tolerance_days = 3     # Date range for duplicate checking
        
    def detect_duplicates_in_extraction(self, extracted_bookings: List[Dict], existing_df: pd.DataFrame) -> Dict:
        """
        Detect duplicates in extracted bookings and provide filtering options
        
        Args:
            extracted_bookings: List of bookings from AI extraction
            existing_df: DataFrame of existing bookings in database
            
        Returns:
            Dict with duplicate analysis and filtering recommendations
        """
        print(f"🔍 [AI_DUPLICATE] Analyzing {len(extracted_bookings)} extracted bookings...")
        
        results = {
            'total_extracted': len(extracted_bookings),
            'duplicates_found': 0,
            'new_bookings': 0,
            'bookings_analysis': [],
            'recommendations': [],
            'filtered_bookings': [],
            'duplicate_groups': []
        }
        
        for i, booking in enumerate(extracted_bookings):
            analysis = self._analyze_single_booking(booking, existing_df, i)
            results['bookings_analysis'].append(analysis)
            
            if analysis['is_duplicate']:
                results['duplicates_found'] += 1
                # Add to duplicate groups for detailed review
                results['duplicate_groups'].append({
                    'extracted_booking': booking,
                    'matching_existing': analysis['matches'],
                    'confidence': analysis['confidence'],
                    'recommendation': analysis['recommendation']
                })
            else:
                results['new_bookings'] += 1
                results['filtered_bookings'].append(booking)
        
        # Generate AI recommendations
        results['recommendations'] = self._generate_ai_recommendations(results)
        
        print(f"✅ [AI_DUPLICATE] Analysis complete: {results['new_bookings']} new, {results['duplicates_found']} duplicates")
        
        return results
    
    def _analyze_single_booking(self, booking: Dict, existing_df: pd.DataFrame, index: int) -> Dict:
        """Analyze a single booking for duplicates"""
        
        analysis = {
            'index': index,
            'booking': booking,
            'is_duplicate': False,
            'confidence': 0.0,
            'matches': [],
            'recommendation': 'add',  # add, skip, review
            'reasons': []
        }
        
        guest_name = (booking.get('guest_name') or '').strip()
        checkin_date = booking.get('checkin_date') or booking.get('check_in_date', '')
        booking_id = (booking.get('booking_id') or '').strip()
        
        if not guest_name:
            analysis['recommendation'] = 'review'
            analysis['reasons'].append('Missing guest name')
            return analysis
        
        # Check for exact booking ID match
        if booking_id and not existing_df.empty:
            booking_id_matches = existing_df[
                existing_df['Số đặt phòng'].astype(str).str.contains(booking_id, na=False, case=False)
            ]
            
            if not booking_id_matches.empty:
                analysis['is_duplicate'] = True
                analysis['confidence'] = 1.0
                analysis['recommendation'] = 'skip'
                analysis['reasons'].append(f'Exact booking ID match: {booking_id}')
                analysis['matches'] = booking_id_matches.to_dict('records')
                return analysis
        
        # Check for name and date similarity
        if not existing_df.empty and checkin_date:
            try:
                checkin_dt = pd.to_datetime(checkin_date)
                date_range_start = checkin_dt - pd.Timedelta(days=self.date_tolerance_days)
                date_range_end = checkin_dt + pd.Timedelta(days=self.date_tolerance_days)
                
                # Filter by date range first
                date_filtered = existing_df[
                    (pd.to_datetime(existing_df['Check-in Date']) >= date_range_start) &
                    (pd.to_datetime(existing_df['Check-in Date']) <= date_range_end)
                ]
                
                if not date_filtered.empty:
                    # Check name similarity
                    for _, existing_booking in date_filtered.iterrows():
                        existing_name = str(existing_booking.get('Tên người đặt', '')).strip()
                        similarity = self._calculate_name_similarity(guest_name, existing_name)
                        
                        if similarity >= self.similarity_threshold:
                            analysis['is_duplicate'] = True
                            analysis['confidence'] = similarity
                            analysis['matches'].append(existing_booking.to_dict())
                            analysis['reasons'].append(
                                f'Name similarity {similarity:.1%}: "{guest_name}" ≈ "{existing_name}"'
                            )
                            
                            if similarity >= 0.95:
                                analysis['recommendation'] = 'skip'
                            else:
                                analysis['recommendation'] = 'review'
                                
            except Exception as e:
                print(f"⚠️ [AI_DUPLICATE] Date analysis error: {e}")
                analysis['reasons'].append('Date parsing error')
        
        return analysis
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names using multiple methods"""
        
        name1_clean = self._clean_name(name1)
        name2_clean = self._clean_name(name2)
        
        if not name1_clean or not name2_clean:
            return 0.0
        
        # Exact match
        if name1_clean == name2_clean:
            return 1.0
        
        # Sequence matcher similarity
        seq_similarity = difflib.SequenceMatcher(None, name1_clean, name2_clean).ratio()
        
        # Token-based similarity (for names with different word order)
        tokens1 = set(name1_clean.split())
        tokens2 = set(name2_clean.split())
        if tokens1 and tokens2:
            token_similarity = len(tokens1.intersection(tokens2)) / len(tokens1.union(tokens2))
        else:
            token_similarity = 0.0
        
        # Combined similarity score
        combined_similarity = max(seq_similarity, token_similarity * 0.9)
        
        return combined_similarity
    
    def _clean_name(self, name: str) -> str:
        """Clean and normalize name for comparison"""
        if not name:
            return ""
        
        # Remove extra spaces, normalize case
        cleaned = re.sub(r'\s+', ' ', str(name).strip().lower())
        
        # Remove common prefixes/suffixes
        prefixes = ['mr.', 'mrs.', 'ms.', 'dr.', 'prof.']
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        return cleaned
    
    def _generate_ai_recommendations(self, results: Dict) -> List[str]:
        """Generate smart recommendations based on analysis"""
        recommendations = []
        
        total = results['total_extracted']
        duplicates = results['duplicates_found']
        new_bookings = results['new_bookings']
        
        if duplicates == 0:
            recommendations.append(f"✅ All {total} bookings appear to be new - safe to add all")
        
        elif duplicates == total:
            recommendations.append(f"⚠️ All {total} bookings appear to be duplicates - review carefully")
            recommendations.append("💡 Consider if this is a different date range or updated booking information")
        
        else:
            recommendations.append(f"📊 Found {new_bookings} new bookings and {duplicates} potential duplicates")
            recommendations.append(f"✅ Recommend adding {new_bookings} new bookings automatically")
            recommendations.append(f"👀 Review {duplicates} duplicates manually before adding")
        
        # Check for high-confidence duplicates
        high_confidence_dups = sum(1 for analysis in results['bookings_analysis'] 
                                  if analysis['is_duplicate'] and analysis['confidence'] >= 0.95)
        
        if high_confidence_dups > 0:
            recommendations.append(f"🚫 {high_confidence_dups} bookings are very likely duplicates - recommend skipping")
        
        # Check for booking ID patterns
        booking_ids = [booking.get('booking_id', '') for booking in results.get('filtered_bookings', [])]
        unique_ids = set(filter(None, booking_ids))
        
        if len(booking_ids) != len(unique_ids):
            recommendations.append("⚠️ Duplicate booking IDs found within extracted data - review for conflicts")
        
        return recommendations
    
    def create_filtered_response(self, extracted_bookings: List[Dict], existing_df: pd.DataFrame) -> Dict:
        """Create a complete filtered response with all analysis"""
        
        duplicate_analysis = self.detect_duplicates_in_extraction(extracted_bookings, existing_df)
        
        response = {
            'success': True,
            'total_extracted': len(extracted_bookings),
            'analysis': duplicate_analysis,
            'filtering_options': {
                'add_all_new': {
                    'count': duplicate_analysis['new_bookings'],
                    'bookings': duplicate_analysis['filtered_bookings'],
                    'description': 'Add only new bookings (recommended)'
                },
                'add_all_extracted': {
                    'count': len(extracted_bookings),
                    'bookings': extracted_bookings,
                    'description': 'Add all extracted bookings (may include duplicates)'
                },
                'manual_review': {
                    'count': duplicate_analysis['duplicates_found'],
                    'duplicates': duplicate_analysis['duplicate_groups'],
                    'description': 'Review duplicates manually'
                }
            },
            'recommendations': duplicate_analysis['recommendations']
        }
        
        return response

# Global instance
ai_duplicate_detector = AIDuplicateDetector()