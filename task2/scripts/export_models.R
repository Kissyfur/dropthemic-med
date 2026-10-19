# Export the PETRIMED models used here to xgboost JSON, for Python: the pico (0.2-3 um) psbO models
# of each PST with a validation correlation of at least MIN_COR, the ones PETRIMED averages.
#
#   Rscript task2/scripts/export_models.R
#
# Writes task2/data/models/<PST>.jsonl, one model per line, and a summary.csv. Needs the xgboost
# package (install.packages("xgboost")); the models were saved with xgboost >= 2.

suppressMessages(library(xgboost))
MIN_COR <- 0.6
prefix <- "task2/PETRIMED/MODELS/psbo_pico"
dir_out <- "task2/data/models"

models <- readRDS(paste0(prefix, "_models.RData"))
info <- readRDS(paste0(prefix, "_models_info.RData"))
dir.create(dir_out, recursive = TRUE, showWarnings = FALSE)
summary <- data.frame()
for (pst in names(models)) {
  if (!is.data.frame(info[[pst]])) next
  keep <- !is.na(info[[pst]]$cor_valid) & info[[pst]]$cor_valid >= MIN_COR
  if (!any(keep)) next
  ids <- info[[pst]]$model_id[keep]
  json <- vapply(models[[pst]][ids], function(b) rawToChar(xgb.save.raw(b, raw_format = "json")), "")
  writeLines(json, file.path(dir_out, paste0(pst, ".jsonl")))
  summary <- rbind(summary, data.frame(pst = pst, models = sum(keep), cor_valid = mean(info[[pst]]$cor_valid[keep])))
}
write.csv(summary, file.path(dir_out, "summary.csv"), row.names = FALSE)
print(summary, digits = 2)
