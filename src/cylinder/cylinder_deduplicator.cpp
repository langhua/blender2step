#include "cylinder_deduplicator.h"
#include <cmath>

std::vector<CylinderCandidate> CylinderDeduplicator::deduplicate(
    std::vector<CylinderCandidate>& cylinders
) {
    if (cylinders.empty()) return cylinders;
    
    std::vector<CylinderCandidate> result;
    std::vector<bool> used(cylinders.size(), false);
    
    for (size_t i = 0; i < cylinders.size(); i++) {
        if (used[i]) continue;
        
        result.push_back(cylinders[i]);
        used[i] = true;
        
        for (size_t j = i + 1; j < cylinders.size(); j++) {
            if (used[j]) continue;
            
            double radius_diff = fabs(cylinders[i].radius - cylinders[j].radius) / ((cylinders[i].radius + cylinders[j].radius) / 2);
            double z_diff = fabs(cylinders[i].axis_point.Z() - cylinders[j].axis_point.Z());
            
            if (radius_diff < 0.03 && z_diff < cylinders[i].cylinder_height * 0.5) {
                if (cylinders[j].face_indices.size() > cylinders[i].face_indices.size()) {
                    result.back() = cylinders[j];
                }
                used[j] = true;
            }
        }
    }
    
    return result;
}
