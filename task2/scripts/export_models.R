# Export the PETRIMED models used here to xgboost JSON, for Python: for each model set, the models of
# each PST with a validation correlation of at least MIN_COR, the ones PETRIMED averages.
#   psbo_pico: psbO genes, pico fraction (0.2-3 um), used on the satellite pigments (Tasks 2 and 4);
#   metab_pico, metab_nano: metabarcoding, pico and nano (3-20 um) fractions, in the units of the VIDA
#   data of Task 3 (% of the eukaryotes or of the prokaryotes).
#
#   Rscript task2/scripts/export_models.R
#
# Writes task2/data/models/<set>/<PST>.jsonl, one model per line, and a summary.csv. Needs the xgboost
# package (install.packages("xgboost")); the models were saved with xgboost >= 2.

suppressMessages(library(xgboost))
MIN_COR <- 0.6
SETS <- c("psbo_pico", "metab_pico", "metab_nano")
dir_in <- "task2/PETRIMED/MODELS"
dir_out <- "task2/data/models"

summary <- data.frame()
for (set in SETS) {
  models <- readRDS(file.path(dir_in, paste0(set, "_models.RData")))
  info <- readRDS(file.path(dir_in, paste0(set, "_models_info.RData")))
  out <- file.path(dir_out, set)
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  for (pst in names(models)) {
    if (!is.data.frame(info[[pst]])) next
    keep <- !is.na(info[[pst]]$cor_valid) & info[[pst]]$cor_valid >= MIN_COR
    if (!any(keep)) next
    ids <- info[[pst]]$model_id[keep]
    json <- vapply(models[[pst]][ids], function(b) rawToChar(xgb.save.raw(b, raw_format = "json")), "")
    writeLines(json, file.path(out, paste0(pst, ".jsonl")))
    summary <- rbind(summary, data.frame(set = set, pst = pst, models = sum(keep),
                                         cor_valid = mean(info[[pst]]$cor_valid[keep])))
  }
}
write.csv(summary, file.path(dir_out, "summary.csv"), row.names = FALSE)
print(summary, digits = 2)
