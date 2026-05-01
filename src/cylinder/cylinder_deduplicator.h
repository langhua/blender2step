// Cylinder Deduplicator
#ifndef CYLINDER_DEDUPLICATOR_H
#define CYLINDER_DEDUPLICATOR_H

#include "cylinder_types.h"
#include <vector>
#include <cmath>

class CylinderDeduplicator {
public:
    static std::vector<CylinderCandidate> deduplicate(
        std::vector<CylinderCandidate>& cylinders
    );
};

#endif // CYLINDER_DEDUPLICATOR_H
